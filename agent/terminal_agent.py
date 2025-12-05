import os
import yaml
import json
import requests
import re
from pathlib import Path
from huggingface_hub import InferenceClient

# ================= CONFIG =================
HF_TOKEN = os.getenv("HF_API_TOKEN")
if not HF_TOKEN:
    raise RuntimeError("Set HF_API_TOKEN in your environment")

client = InferenceClient(token=HF_TOKEN)

# Project root and config
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

def load_yaml(filename: str):
    filepath = CONFIG_DIR / filename
    try:
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)
        print(f"[INFO] Loaded YAML: {filepath}")
        return data
    except Exception as e:
        print(f"[ERROR] Failed loading YAML {filepath}: {e}")
        return None

# ================= MCP CLIENT - FIXED =================
class MCP:
    # Map logical tool names to MCP server URLs WITH /call endpoint
    servers = {
        "shell":  "http://localhost:8001",
        "fs":     "http://localhost:8002",
        "fetch":  "http://localhost:8003",
        "python": "http://localhost:8004",
    }

    @classmethod
    def execute(cls, tool_call: dict):
        """
        FIXED: Your MCP servers expect POST to /call endpoint with:
        {
            "name": "tool_name",       # e.g., "bash", "read", "get", "exec"
            "arguments": {...}         # Tool-specific arguments
        }
        """
        server_name = tool_call.get("tool_call")  # "shell", "fs", etc.
        if server_name not in cls.servers:
            return {"error": f"Unknown MCP server: {server_name}"}

        # Map endpoint to actual tool names YOUR servers use
        endpoint = tool_call.get("endpoint", "/exec")
        
        # Your servers use these tool names:
        if server_name == "shell":
            tool_name = "bash"
            arguments = {"prompt": tool_call.get("payload", {}).get("command", "")}
        elif server_name == "fs":
            if endpoint == "/read":
                tool_name = "read"
                arguments = {"path": tool_call.get("payload", {}).get("path", "")}
            else:  # /write
                tool_name = "write"
                arguments = {
                    "path": tool_call.get("payload", {}).get("path", ""),
                    "content": tool_call.get("payload", {}).get("content", "")
                }
        elif server_name == "fetch":
            tool_name = "get"
            arguments = {"url": tool_call.get("payload", {}).get("url", "")}
        elif server_name == "python":
            tool_name = "exec"
            arguments = {"code": tool_call.get("payload", {}).get("code", "")}
        else:
            tool_name = endpoint.replace("/", "")
            arguments = tool_call.get("payload", {})
        
        # Build CORRECT payload for YOUR servers
        payload = {
            "name": tool_name,
            "arguments": arguments
        }
        
        url = f"{cls.servers[server_name]}/call"  # FIXED: Use /call endpoint
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "error": f"MCP call failed: {str(e)}",
                "server": server_name,
                "url": url,
                "payload": payload
            }

# ================= LLM BRAIN =================
def call_llm(system_prompt: str, user_prompt: str, max_tokens=512):
    """
    Calls HF InferenceClient to get the primary action
    Output must follow the YAML: single best SQL/BASH/JSON block
    """
    resp = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0,
        max_tokens=max_tokens
    )
    return resp.choices[0].message.content

# ================= TOOL EXTRACTION - FIXED =================
def extract_tool_call(text: str):
    """
    FIXED: Extract JSON from code blocks properly
    Your agent outputs:
    ```json
    {"tool_call": "shell", "endpoint": "/exec", "payload": {"command": "ls"}}
    ```
    """
    # Look for JSON code block
    json_match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Also try to find any JSON in the text
    try:
        # Look for {...} pattern
        json_pattern = r'\{[^{}]*"tool_call"[^{}]*\}'
        match = re.search(json_pattern, text)
        if match:
            return json.loads(match.group())
    except:
        pass
    
    return None

# ================= DEBUG MCP =================
def debug_mcp_connection():
    """Test if MCP servers are reachable"""
    print("\n🧪 DEBUG: Testing MCP servers...")
    
    for server, base_url in MCP.servers.items():
        print(f"\n  Testing {server} server:")
        
        # Test /health
        try:
            resp = requests.get(f"{base_url}/health", timeout=2)
            print(f"    GET /health: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"    GET /health: FAILED - {e}")
            return False
        
        # Test that server exists
        try:
            resp = requests.get(base_url, timeout=2)
            print(f"    GET /: {resp.status_code}")
        except:
            print(f"    GET /: No response (but /health works)")
    
    # Test actual MCP call
    print("\n  Testing sample MCP call:")
    test_call = {
        "tool_call": "shell",
        "endpoint": "/exec",
        "payload": {"command": "echo 'MCP test'"}
    }
    
    result = MCP.execute(test_call)
    print(f"    Result: {result}")
    
    return "error" not in str(result).lower()

# ================= TERMINAL AGENT =================
def terminal_agent(user_input: str, cfg: dict):
    """
    Main agent loop:
    1. Send user input to LLM (brain)
    2. LLM decides primary tool and generates minimal command/query
    3. Extract MCP call JSON and send to correct MCP server
    4. Show result
    """
    system_prompt = cfg["terminal_agent"]["system_prompt"]
    user_template = cfg["terminal_agent"]["user_prompt"]
    user_prompt = user_template.replace("{{user_input}}", user_input)

    # Step 1: LLM decides what to do
    print("\n[LLM THINKING...]")
    llm_output = call_llm(system_prompt, user_prompt)
    print("[LLM OUTPUT]:")
    print(llm_output)

    # Step 2: Extract tool call JSON
    tool_call = extract_tool_call(llm_output)
    
    if not tool_call:
        print("\n❌ No tool call detected in LLM output")
        print("LLM might have output bash/sql directly instead of JSON")
        
        # Try to extract bash command directly
        bash_match = re.search(r'```bash\n(.*?)\n```', llm_output, re.DOTALL)
        if bash_match:
            print("\n⚠️ Found bash command, converting to MCP call...")
            tool_call = {
                "tool_call": "shell",
                "endpoint": "/exec",
                "payload": {"command": bash_match.group(1).strip()}
            }
        else:
            return

    print(f"\n[EXTRACTED TOOL CALL]: {tool_call}")

    # Step 3: Execute with MCP
    print("\n[EXECUTING VIA MCP...]")
    mcp_result = MCP.execute(tool_call)
    
    # Step 4: Show result
    print("\n[MCP RESULT]:")
    print(json.dumps(mcp_result, indent=2))

# ================= ENTRY POINT =================
def main():
    print("🚀 Starting Terminal Agent with MCP Integration")
    
    # Debug MCP connection first
    if not debug_mcp_connection():
        print("\n❌ MCP servers not ready!")
        print("Make sure servers are running:")
        print("  docker ps")
        print("If not, run: docker start shell-server fs-server fetch-server python-server")
        return
    
    # Load config
    cfg = load_yaml("hier_terminal_prompts.yaml")
    if cfg is None:
        return
    
    # Example usage
    print("\n" + "="*50)
    user_input = "List files in current directory"
    print(f"QUERY: {user_input}")
    print("="*50)
    
    terminal_agent(user_input, cfg)

if __name__ == "__main__":
    main()