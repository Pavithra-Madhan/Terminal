import os
import requests
import json
import yaml

# --- Configuration (Hugging Face) ---
HF_TOKEN = os.environ.get("HUGGINGFACE_TOKEN")
if not HF_TOKEN:
    print("FATAL: HUGGINGFACE_TOKEN environment variable not set.")
    exit()

# Use YOUR Llama-4-Scout model
HF_MODEL = "meta-llama/Llama-4-Scout-17B-16E-Instruct"

# --- Tool Definitions ---
TOOLS = [
    {"name": "SHELL_COMMAND", "port": 8001, "endpoint": "/execute_shell"},
    {"name": "SYSTEM_SQLITE", "port": 8002, "endpoint": "/execute_query"},
    {"name": "PYTHON_EVAL", "port": 8003, "endpoint": "/execute_python"},
    {"name": "FETCH_WEB", "port": 8004, "endpoint": "/fetch_url"},
]

HOST_URL = "http://localhost"

# --- Helper Functions ---
def load_tools_from_yaml():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'hier_terminal_prompts.yaml')
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('terminal_agent', {}).get('system_prompt', 'Default prompt')
    except FileNotFoundError:
        return "You are a specialized debugging and execution agent."

def call_hf_model(system_prompt, user_input):
    """Call Hugging Face Router API (the correct endpoint)."""
    # ✅ CORRECT ENDPOINT: Use router.huggingface.co
    url = "https://router.huggingface.co/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Format messages for chat model
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]
    
    payload = {
        "model": HF_MODEL,
        "messages": messages,
        "max_tokens": 1000,
        "temperature": 0.0,
        "stream": False
    }
    
    try:
        print(f"Calling model: {HF_MODEL}")
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        print(f"Response Status: {response.status_code}")
        
        response.raise_for_status()
        result = response.json()
        
        # Extract response
        generated_text = result["choices"][0]["message"]["content"]
        print("✓ API call successful")
        return generated_text
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return "Error 401: Unauthorized. Check your HUGGINGFACE_TOKEN."
        elif e.response.status_code == 404:
            return f"Error 404: Model '{HF_MODEL}' not found via router."
        elif e.response.status_code == 503:
            return f"Error 503: Model loading. Try again in 30s."
        elif e.response.status_code == 429:
            return "Error 429: Rate limited. Wait a minute."
        else:
            try:
                error_detail = e.response.json()
                return f"HTTP Error {e.response.status_code}: {error_detail}"
            except:
                return f"HTTP Error {e.response.status_code}"
                
    except KeyError as e:
        return f"Parse error: {e}. Response: {result if 'result' in locals() else 'N/A'}"
    except Exception as e:
        return f"Error: {str(e)}"

# ... keep the rest of your functions unchanged (parse_and_execute_action, terminal_agent_dispatcher, etc.)

# --- Main Test ---
if __name__ == "__main__":
    test_query = (
        "I'm getting 'Connection refused' errors when trying to query the system database. "
        "The FastAPI server log shows it started on port 8000, but my app gets errors on localhost:8002. "
        "Docker Compose shows the sqlite_mcp container is running. "
        "Diagnose the networking issue."
    )
    
    print("\n" + "="*60)
    print(f"USER QUERY: {test_query}")
    print("="*60)
    
    # Direct test to see what we get
    system_prompt = load_tools_from_yaml()
    print("--- Calling LLM ---")
    output = call_hf_model(system_prompt, test_query)
    print(f"\nRAW OUTPUT:\n{output}")
    
    # Quick check
    if "### PRIMARY ACTION" in output:
        print("\n✓ Format looks good!")
    else:
        print("\n⚠️  No PRIMARY ACTION found.")