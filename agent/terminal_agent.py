import os
import requests
import json
import yaml
from huggingface_hub import InferenceClient

# --- Configuration (Hugging Face API) ---

# You MUST set this in your terminal:
# export HUGGINGFACEHUB_API_TOKEN="hf_xxx"
HF_API_TOKEN = os.environ.get("HUGGINGFACEHUB_API_TOKEN")

if not HF_API_TOKEN:
    print("FATAL: HUGGINGFACEHUB_API_TOKEN environment variable not set.")
    exit()

# Fast, strong instruction-following model
HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"

# --- Tool Definitions (MCP Service Endpoints) ---

HOST_URL = "http://localhost" 

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

# Function to dynamically generate the LLM's system prompt
def generate_system_prompt(tools):
    tool_descriptions = "\n\n".join([
        f"Tool Name: {tool['name']}\nPurpose: {tool['purpose']}\nEndpoint: {tool['endpoint']}"
        for tool in tools
    ])

    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'hier_terminal_prompts.yaml')
        with open(config_path, 'r') as f:
            yaml_config = yaml.safe_load(f)
            core_instruction = yaml_config.get(
                'ROLE',
                yaml_config.get(
                    'system_prompt',
                    'You are a specialized debugging and execution agent...'
                )
            )
    except Exception:
        core_instruction = (
            "You are a specialized debugging and execution agent. "
            "You must act as a Terminal Agent Dispatcher. "
            "Analyze the user's request and formulate a multi-step plan "
            "based on tool hierarchy."
        )

    system_prompt = f"""
{core_instruction}

--- AVAILABLE TOOLS ---
{tool_descriptions}

--- HIERARCHY OF TOOL USAGE (PRIORITY) ---
1. SYSTEM_SQLITE
2. PYTHON_EVAL / SHELL_COMMAND
3. FETCH_WEB
4. RAG / CHROMA

--- RESPONSE FORMAT ---
You MUST output:
### PRIMARY ACTION (Executable):
### FALLBACK STEPS (Hierarchy):
"""
    return system_prompt


# --- HF LLM CALL (REPLACEMENT FOR GEMINI) ---
def get_execution_plan(user_input, system_prompt):
    print("--- Calling Hugging Face Inference API ---")

    try:
        client = InferenceClient(
            model=HF_MODEL,
            token=HF_API_TOKEN
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": "Understood. I will follow the hierarchy and structured format."},
            {"role": "user", "content": user_input}
        ]

        response = client.chat_completion(
            messages=messages,
            temperature=0.0,
            max_tokens=1024
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"LLM Error: {e}"


# --- PRIMARY ACTION EXECUTOR (UNCHANGED) ---
def execute_primary_action(plan_output):
    
    if "### PRIMARY ACTION (Executable):" not in plan_output:
        return {"result": "Could not parse PRIMARY ACTION from LLM output."}

    action_block = plan_output.split(
        "### PRIMARY ACTION (Executable):"
    )[1].split(
        "### FALLBACK STEPS (Hierarchy):"
    )[0].strip()
    
    print(f"\n--- DEBUG: Raw action block ---\n{action_block}")
    
    # 🔥 FIXED: Handle the #### SYSTEM_SQLITE header properly
    if "```sql" in action_block or "SYSTEM_SQLITE" in action_block:
        tool_name = "SYSTEM_SQLITE"
        
        # FIRST: Remove markdown headers (#### SYSTEM_SQLITE)
        cleaned = action_block.replace("#### SYSTEM_SQLITE", "").replace("# SYSTEM_SQLITE", "")
        
        # THEN: Extract SQL from code blocks
        if "```sql" in cleaned:
            # Extract between ```sql and ```
            parts = cleaned.split("```sql")
            if len(parts) > 1:
                command = parts[1].split("```")[0].strip()
            else:
                command = cleaned.replace("```sql", "").replace("```", "").strip()
        else:
            # No code blocks, just clean up
            command = cleaned.replace("SYSTEM_SQLITE:", "").replace("SYSTEM_SQLITE", "").strip()
        
        mcp = next(t for t in TOOLS if t["name"] == tool_name)
        api_data = {"query": command, "db_name": "system"}
        
        print(f"--- DEBUG: Cleaned command ---\n{command}")

    elif action_block.startswith("```bash") or "SHELL_COMMAND" in action_block:
        tool_name = "SHELL_COMMAND"
        command = (
            action_block.replace("```bash", "")
            .replace("```", "")
            .replace(f"{tool_name}:", "")
            .replace(f"#### {tool_name}", "")
            .replace(f"# {tool_name}", "")
            .strip()
        )
        mcp = next(t for t in TOOLS if t["name"] == tool_name)
        api_data = {"command": command}

    elif "rationale" in action_block.lower():
        return {"result": action_block}

    else:
        return {"result": f"Unknown action format: {action_block}"}

    print(f"\n--- EXECUTING {mcp['name']} ---")
    print(f"Final Command: '{command}'")
    print(f"Payload: {json.dumps(api_data, indent=2)}")

    try:
        url = f"{HOST_URL}:{mcp['port']}{mcp['endpoint']}"
        print(f"URL: {url}")
        
        response = requests.post(url, json=api_data, timeout=10)
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 403:
            # Get more details about the 403
            try:
                error_detail = response.json()
                return {
                    "error": "403 Forbidden from server",
                    "detail": error_detail,
                    "payload_sent": api_data
                }
            except:
                return {
                    "error": f"403 Forbidden (no details)",
                    "status_code": 403,
                    "payload_sent": api_data
                }
        
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


# --- MAIN DISPATCHER (UNCHANGED) ---
def terminal_agent_dispatcher(user_input):
    print("--- 1. Generating System Prompt ---")
    system_prompt = generate_system_prompt(TOOLS)

    print("\n--- 2. Requesting LLM Plan ---")
    plan_output = get_execution_plan(user_input, system_prompt)
    print("\n" + plan_output)

    print("\n--- 3. Executing Primary Action ---")
    action_result = execute_primary_action(plan_output)

    print("\n--- PRIMARY ACTION RESULT ---")
    print(json.dumps(action_result, indent=2))


if __name__ == "__main__":
    test_query = (
        "I need to confirm the database connectivity. "
        "Run a simple query against the file_metadata table "
        "to retrieve the path and last modified time for all records."
    )

    print("\n=======================================================")
    print(f"USER QUERY: {test_query}")
    print("=======================================================")

    terminal_agent_dispatcher(test_query)

    print("\n=======================================================")
    print("DEMONSTRATION COMPLETE.")
    print("=======================================================")

