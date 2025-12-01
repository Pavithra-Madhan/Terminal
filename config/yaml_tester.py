import os
import yaml
import json
from pathlib import Path
from huggingface_hub import InferenceClient

# ==============================================================================  
# CONFIG
# ==============================================================================  

HF_TOKEN = os.getenv("HF_API_TOKEN")
if not HF_TOKEN:
    raise RuntimeError("Please set HF_API_TOKEN in your environment.")

client = InferenceClient(token=HF_TOKEN)

PROJECT_ROOT = Path(__file__).parent
CONFIG_DIR = PROJECT_ROOT  # assuming YAMLs are in the same folder

def load_yaml(filepath: Path):
    try:
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)
        print(f"[INFO] Loaded YAML: {filepath.name}")
        return data
    except Exception as e:
        print(f"[ERROR] Failed loading YAML {filepath}: {e}")
        return None

# ==============================================================================  
# MODEL CALL
# ==============================================================================  

def call_model(system_prompt: str, user_prompt: str, max_tokens=512):
    resp = client.chat.completions.create(
        model="meta-llama/Llama-4-Scout-17B-16E-Instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0,
        max_tokens=max_tokens
    )
    return resp.choices[0].message.content

# ==============================================================================  
# TEST FUNCTIONS
# ==============================================================================  

def test_memory_agent(cfg):
    print("\n===== MEMORY AGENT TEST =====")
    sys_prompt = cfg["memory_prompts"]["memory_agent"]["system_prompt"]
    user_template = cfg["memory_prompts"]["memory_agent"]["user_prompt"]

    test_input = "I'm actually allergic to penicillin, so never suggest any medications"
    user_prompt = user_template.replace("{{user_input}}", test_input)

    output = call_model(sys_prompt, user_prompt)
    print("User Input:", test_input)
    print("Output:\n", output)

def test_terminal_agent(cfg):
    print("\n===== TERMINAL AGENT TEST =====")
    sys_prompt = cfg["terminal_prompts"]["terminal_agent"]["system_prompt"]
    user_template = cfg["terminal_prompts"]["terminal_agent"]["user_prompt"]

    test_input = """Explain the design rationale behind using the custom 'Hyperdrive' caching layer instead of Redis in the Authentication microservice. Include the specific trade-offs we accepted for performance, and cite the architectural decision document."""
    user_prompt = user_template.replace("{{user_input}}", test_input)

    output = call_model(sys_prompt, user_prompt)
    print("User Input:", test_input)
    print("Output:\n", output)
    """"

    rag_bundle = {
        "curated_context": ["User wants project file structure."],
        "needed_action": "list_files",
        "path": "."
    }
    user_prompt = user_template.replace("{{rag_output}}", json.dumps(rag_bundle, indent=2))
    output = call_model(sys_prompt, user_prompt)
    print("Simulated RAG Output:", rag_bundle)
    print("Output:\n", output)
"""

# ==============================================================================  
# MAIN
# ==============================================================================  

def main():
    print("\n=== Loading YAML Configs ===")
    config_files = {
        "memory_prompts": CONFIG_DIR / "memory_prompts.yaml",
        "terminal_prompts": CONFIG_DIR / "defensive_terminal_prompts.yaml",
    }

    configs = {}
    for key, path in config_files.items():
        print(f"Loading → {path}")
        data = load_yaml(path)
        if not data:
            print("❌ Stopping due to YAML load error.")
            return
        configs[key] = data

    print("\n=== Starting Tests ===")
    #test_memory_agent(configs)
    #test_rag_agent(configs)
    test_terminal_agent(configs)
    #test_coordination(configs)

if __name__ == "__main__":
    main()