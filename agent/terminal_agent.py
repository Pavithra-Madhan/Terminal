import os
import requests 
import json
import yaml 
from google import genai
from google.genai.errors import APIError

# --- Configuration (Gemini API) ---

# Get your API key from environment variable
# You MUST set this in your terminal: export GEMINI_API_KEY="AIzaSy...your...key...here"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("FATAL: GEMINI_API_KEY environment variable not set. Please get a key from Google AI Studio and set it.")
    exit()

# The model known for speed and great instruction following
GEMINI_MODEL = "gemini-2.5-flash" 

# --- Tool Definitions (MCP Service Endpoints) ---

# NOTE: The host is 'host.docker.internal' so the agent running locally
# can connect to the services running inside the Docker network (after the docker-compose fix).
# FINAL FIX: Using the verified Docker Gateway IP to bypass NameResolutionError
HOST_URL = "http://172.18.0.1"

# The list of your four Microservice Control Protocol (MCP) tools
TOOLS = [
    {
        "name": "SHELL_COMMAND",
        "purpose": "Execute arbitrary BASH commands (ls, find, cat, git, etc.) in a sandboxed, read-only filesystem to check live system state, file existence, and permissions. Use this for real-time filesystem checks.",
        "port": 8001,
        "endpoint": "/execute_shell"
    },
    {
        "name": "SYSTEM_SQLITE",
        "purpose": "Query the internal, structured knowledge base (memory.db) for exact facts like port numbers, service configurations, and file metadata (path, purpose). Use this for fast, structured data lookups.",
        "port": 8002,
        "endpoint": "/execute_query"
    },
    {
        "name": "PYTHON_EVAL",
        "purpose": "Execute complex or large Python code snippets for calculations, data manipulation, or advanced string processing. The output is the value of the 'result' variable.",
        "port": 8003,
        "endpoint": "/execute_python"
    },
    {
        "name": "FETCH_WEB",
        "purpose": "Fetch the content of a public URL (web page) for external documentation or up-to-date information.",
        "port": 8004,
        "endpoint": "/fetch_url"
    },
]

# Function to dynamically generate the LLM's system prompt from the tools list and YAML
def generate_system_prompt(tools):
    tool_descriptions = "\n\n".join([
        f"Tool Name: {tool['name']}\nPurpose: {tool['purpose']}\nEndpoint: {tool['endpoint']}"
        for tool in tools
    ])

    try:
        # Construct the path to the YAML file relative to the script location
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'hier_terminal_prompts.yaml')
        with open(config_path, 'r') as f:
            yaml_config = yaml.safe_load(f)
            # Assuming your core instruction is under a key like 'ROLE' or 'system_prompt'
            core_instruction = yaml_config.get('ROLE', yaml_config.get('system_prompt', 'You are a specialized debugging and execution agent...'))
    except FileNotFoundError:
        print(f"Error: Config file not found. Using hardcoded instruction.")
        core_instruction = "You are a specialized debugging and execution agent. You must act as a Terminal Agent Dispatcher. Analyze the user's request and formulate a multi-step plan based on tool hierarchy, starting with the most efficient PRIMARY ACTION."
    except Exception as e:
        print(f"Error loading YAML: {e}")
        core_instruction = "You are a specialized debugging and execution agent. You must act as a Terminal Agent Dispatcher. Analyze the user's request and formulate a multi-step plan based on tool hierarchy, starting with the most efficient PRIMARY ACTION."

    # Insert the tool details and the hierarchy instructions into the core prompt
    system_prompt = f"""
    {core_instruction}

    --- AVAILABLE TOOLS ---
    {tool_descriptions}
    
    --- HIERARCHY OF TOOL USAGE (PRIORITY) ---
    1. **SYSTEM_SQLITE**: For fast, structured fact-checks (ports, configs, file metadata).
    2. **PYTHON_EVAL/SHELL_COMMAND**: For immediate, verifiable action/state checks (calculations, 'ls', 'git log').
    3. **FETCH_WEB**: For external, real-time data.
    4. **RAG/CHROMA**: For deep, semantic search in unstructured knowledge (documentation, incident reports).

    --- RESPONSE FORMAT ---
    You MUST output a two-part response following this structure:
    1. A section starting with '### PRIMARY ACTION (Executable):' containing your single, immediate, most efficient command (SQL or BASH) or a brief rationale.
    2. A section starting with '### FALLBACK STEPS (Hierarchy):' containing the remaining steps of the multi-step plan, prioritized by the hierarchy above, complete with the suggested command or query for each step.
    """
    return system_prompt

# Function to call the LLM and get the structured plan
def get_execution_plan(user_input, system_prompt):
    print("--- Calling Google Gemini API (Free Tier) ---")
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "Understood. I will follow the hierarchy and structured format."}]},
                {"role": "user", "parts": [{"text": user_input}]}
            ],
            config={"temperature": 0.0}
        )
        
        return response.text
    except APIError as e:
        return f"LLM Error: Failed to generate response from Gemini API. Check your GEMINI_API_KEY and ensure access. Error: {e}"
    except Exception as e:
        return f"LLM Error: An unexpected error occurred: {e}"


# Function to execute the PRIMARY ACTION (THIS IS THE CORRECTED PARSER)
def execute_primary_action(plan_output):
    
    if "### PRIMARY ACTION (Executable):" not in plan_output:
        return {"result": "Could not parse PRIMARY ACTION from LLM output. LLM did not follow the required output format."}

    # Extract the primary action block
    action_block = plan_output.split("### PRIMARY ACTION (Executable):")[1].split("### FALLBACK STEPS (Hierarchy):")[0].strip()

    # --- START OF THE FIX: ROBUST PARSING ---
    
    # 1. Check for SQLITE action (using SQL code block or tool name)
    if action_block.startswith("```sql") or "SYSTEM_SQLITE" in action_block:
        tool_name = 'SYSTEM_SQLITE'
        # Clean the command: remove code fences, tool name, and strip whitespace.
        command = action_block.replace("```sql", "").replace("```", "").replace(f"{tool_name}:", "").strip()
        mcp = next(t for t in TOOLS if t['name'] == tool_name)
        api_data = {"query": command}
    
    # 2. Check for SHELL_COMMAND action (using BASH code block or tool name)
    elif action_block.startswith("```bash") or "SHELL_COMMAND" in action_block:
        tool_name = 'SHELL_COMMAND'
        # Clean the command: remove code fences, tool name, and strip whitespace.
        command = action_block.replace("```bash", "").replace("```", "").replace(f"{tool_name}:", "").strip()
        mcp = next(t for t in TOOLS if t['name'] == tool_name)
        api_data = {"command": command}
    
    # 3. Handle other tools/formats (PYTHON_EVAL, FETCH_WEB etc. would be added here)
    # For now, we only handle the primary action types generated by the LLM
    elif 'rationale' in action_block.lower() or 'no command' in action_block.lower():
        return {"result": f"Primary Action is a rationale only (no executable command detected). Action: {action_block}"}
    
    else:
        # Final safety net for unrecognizable format
        return {"result": f"Primary Action is an unknown command format. No execution performed. Action: {action_block}"}

    # --- END OF THE FIX ---

    print(f"\n--- EXECUTING {mcp['name']} ---")
    print(f"Command: {command}")
    
    try:
        # Construct the full URL for the MCP
        url = f"{HOST_URL}:{mcp['port']}{mcp['endpoint']}"
        
        response = requests.post(url, json=api_data, timeout=10)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        
        return response.json()

    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to connect to {mcp['name']} ({url}). Ensure Docker services are running and 'host.docker.internal' is correctly configured in docker-compose. Error: {e}"}

# Main Dispatcher Logic
def terminal_agent_dispatcher(user_input):
    print("--- 1. Generating System Prompt and Tool Configuration ---")
    system_prompt = generate_system_prompt(TOOLS)
    
    print("\n--- 2. Requesting LLM Reasoning and Action Plan ---")
    plan_output = get_execution_plan(user_input, system_prompt)
    print("\n" + plan_output)

    print("\n--- 3. Executing Primary Action ---")
    action_result = execute_primary_action(plan_output)
    
    print("\n--- PRIMARY ACTION RESULT (New Context) ---")
    print(json.dumps(action_result, indent=2))
    

if __name__ == "__main__":
    # The complex debugging query that forces the LLM to use its hierarchy
    test_query = "I need to confirm the database connectivity. Run a simple query against the file_metadata table in the database to retrieve the path and last modified time for all records."
    
    print("\n=======================================================")
    print(f"USER QUERY: {test_query}")
    print("=======================================================")
    
    # Ensure your Docker services are UP before running this!
    terminal_agent_dispatcher(test_query)
    
    print("\n=======================================================")
    print("DEMONSTRATION COMPLETE.")
    print("=======================================================")