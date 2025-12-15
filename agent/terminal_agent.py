import os
import requests
import json
import yaml
from huggingface_hub import InferenceClient

HF_API_TOKEN = os.environ.get("HUGGINGFACEHUB_API_TOKEN")
if not HF_API_TOKEN:
    print("FATAL: HUGGINGFACEHUB_API_TOKEN environment variable not set.")
    exit()

HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"
HOST_URL = "http://localhost"

TOOLS = [
    {
        "name": "SHELL_COMMAND",
        "purpose": "Execute BASH commands to check live system state, file existence, and permissions.",
        "port": 8001,
        "endpoint": "/execute_shell"
    },
    {
        "name": "SYSTEM_SQLITE",
        "purpose": "Query the internal knowledge base for exact facts like file metadata, ports, configurations.",
        "port": 8002,
        "endpoint": "/execute_query"
    },
    {
        "name": "PYTHON_EVAL",
        "purpose": "Execute Python code for calculations, data manipulation, or string processing.",
        "port": 8003,
        "endpoint": "/execute_python"
    },
    {
        "name": "FETCH_WEB",
        "purpose": "Fetch content from public URLs for documentation or external information.",
        "port": 8004,
        "endpoint": "/fetch_url"
    },
]

def generate_system_prompt(tools):
    tool_descriptions = "\n\n".join([
        f"Tool Name: {tool['name']}\nPurpose: {tool['purpose']}\nEndpoint: {tool['endpoint']}"
        for tool in tools
    ])

    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'hier_terminal_prompts.yaml')
        with open(config_path, 'r') as f:
            yaml_config = yaml.safe_load(f)
            core_instruction = yaml_config.get('ROLE', 'You are a specialized debugging and execution agent.')
    except Exception:
        core_instruction = "You are a specialized debugging and execution agent."

    database_schema = """
--- DATABASE SCHEMA (system.db) ---
Table: file_metadata
Columns: path (TEXT), size (INTEGER), last_modified_time (TEXT), purpose (TEXT)

Table: files
Columns: path (TEXT), last_modified (TEXT)

IMPORTANT: For file_metadata table, use 'last_modified_time' column, NOT 'last_modified'.
"""

    system_prompt = f"""
{core_instruction}

{database_schema}

--- AVAILABLE TOOLS ---
{tool_descriptions}

--- HIERARCHY OF TOOL USAGE ---
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

def get_execution_plan(user_input, system_prompt):
    print("--- Calling Hugging Face Inference API ---")
    try:
        client = InferenceClient(model=HF_MODEL, token=HF_API_TOKEN)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": "Understood. I will follow the hierarchy and structured format."},
            {"role": "user", "content": user_input}
        ]
        response = client.chat_completion(messages=messages, temperature=0.0, max_tokens=1024)
        return response.choices[0].message.content
    except Exception as e:
        return f"LLM Error: {e}"

def execute_primary_action(plan_output):
    if "### PRIMARY ACTION (Executable):" not in plan_output:
        return {"result": "Could not parse PRIMARY ACTION from LLM output."}

    action_block = plan_output.split("### PRIMARY ACTION (Executable):")[1]
    if "### FALLBACK STEPS" in action_block:
        action_block = action_block.split("### FALLBACK STEPS")[0]
    action_block = action_block.strip()
    
    print(f"\n--- DEBUG: Raw action block ---\n{action_block}")
    
    if "```sql" in action_block or "SYSTEM_SQLITE" in action_block:
        tool_name = "SYSTEM_SQLITE"
        
        if "```sql" in action_block:
            command = action_block.split("```sql")[1].split("```")[0].strip()
        else:
            command = action_block.replace("#### SYSTEM_SQLITE", "").replace("# SYSTEM_SQLITE", "").replace("SYSTEM_SQLITE:", "").strip()
        
        command = command.rstrip(';').strip()
        
        mcp = next(t for t in TOOLS if t["name"] == tool_name)
        api_data = {"query": command, "db_name": "system"}
        
        print(f"--- DEBUG: Cleaned command ---\n{command}")

    elif "```bash" in action_block or "SHELL_COMMAND" in action_block:
        tool_name = "SHELL_COMMAND"
        if "```bash" in action_block:
            command = action_block.split("```bash")[1].split("```")[0].strip()
        else:
            command = action_block.replace("SHELL_COMMAND:", "").replace("#### SHELL_COMMAND", "").strip()
        command = command.rstrip(';').strip()
        mcp = next(t for t in TOOLS if t["name"] == tool_name)
        api_data = {"command": command}
    else:
        return {"result": f"Unknown format: {action_block}"}

    print(f"\n--- EXECUTING {mcp['name']} ---")
    print(f"Command: {command}")

    try:
        url = f"{HOST_URL}:{mcp['port']}{mcp['endpoint']}"
        response = requests.post(url, json=api_data, timeout=10)
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 400:
            if api_data.get("query", "").endswith(';'):
                api_data["query"] = api_data["query"].rstrip(';').strip()
                print(f"Retrying without semicolon: {api_data['query']}")
                response = requests.post(url, json=api_data, timeout=10)
                print(f"Retry Status: {response.status_code}")
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

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
    test_query = """I'm building a Python microservice that processes user uploads. The service logs show: 
"ERROR: Failed to parse upload metadata. Expected field 'upload_timestamp' missing from row 42."
The upload handler reads from a SQLite table named 'user_uploads' in the 'system' database.
The FastAPI endpoint at /api/uploads returns 500 Internal Server Error when querying uploads from the last 24 hours.
The logs also show Docker container 'upload-processor' restarting every 5 minutes with exit code 137 (OOM killer?).

Diagnose the full stack: database schema, API endpoint, Docker memory, and provide a fix plan."""
    
    print("\n" + "="*60)
    print(f"USER QUERY: {test_query}")
    print("="*60)
    
    terminal_agent_dispatcher(test_query)
    
    print("\n" + "="*60)
    print("DEMONSTRATION COMPLETE.")
    print("="*60)
