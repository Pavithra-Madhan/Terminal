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

    # Multiple test inputs for repetitive testing
    test_inputs = [
        "I'm actually allergic to penicillin, so never suggest any medications",
        "Is it related to my previous symptoms?",
        "I prefer dark mode for all my coding applications",
        "Hello, Parmira! How can you assist me today?",
        "I think I might want to learn Spanish next year"
    ]

    for i, test_input in enumerate(test_inputs, 1):
        print(f"\n--- Test {i} ---")
        user_prompt = user_template.replace("{{user_input}}", test_input)
        output = call_model(sys_prompt, user_prompt)
        print("User Input:", test_input)
        print("Output:\n", output)
        print("-" * 50)

def test_rag_agent(cfg):
    print("\n===== RAG AGENT TEST =====")
    sys_prompt = cfg["rag_prompts"]["rag_agent"]["system_prompt"]
    user_template = cfg["rag_prompts"]["rag_agent"]["user_prompt"]

    mock_data = """
Retrieval request: "What is Parmira's purpose?"

--- MOCK RETRIEVED ---
LTM: Parmira is intended as a multi-agent system.
STM: Focus on Memory + Terminal agents.
SYSTEM: YAML controls routing.
"""
    user_prompt = user_template.replace("{{user_input}}", mock_data)
    output = call_model(sys_prompt, user_prompt)
    print("Mock Retrieval:", mock_data)
    print("Output:\n", output)

def test_terminal_agent(cfg):
    print("\n===== TERMINAL AGENT TEST =====")
    sys_prompt = cfg["terminal_prompts"]["terminal_agent"]["system_prompt"]
    user_template = cfg["terminal_prompts"]["terminal_agent"]["user_prompt"]

    rag_bundle = {
        "curated_context": ["User wants project file structure."],
        "needed_action": "list_files",
        "path": "."
    }
    user_prompt = user_template.replace("{{rag_output}}", json.dumps(rag_bundle, indent=2))
    output = call_model(sys_prompt, user_prompt)
    print("Simulated RAG Output:", rag_bundle)
    print("Output:\n", output)

def test_coordination(cfg):
    print("\n===== COORDINATION TEST =====\n")
    
    # Memory Agent
    mem_sys = cfg["memory_prompts"]["memory_agent"]["system_prompt"]
    mem_user_template = cfg["memory_prompts"]["memory_agent"]["user_prompt"]
    mem_input = "Evaluate the user's plan to integrate Parmira in daily life."
    mem_user_prompt = mem_user_template.replace("{{user_input}}", mem_input)
    mem_out = call_model(mem_sys, mem_user_prompt)
    print("Memory Agent Input:", mem_input)
    print("Memory Agent Output:\n", mem_out)
    
    # RAG Agent
    rag_sys = cfg["rag_prompts"]["rag_agent"]["system_prompt"]
    rag_user_template = cfg["rag_prompts"]["rag_agent"]["user_prompt"]
    rag_input = """
Retrieval request: "What is Parmira's role in user's workflow?"
--- MOCK RETRIEVED ---
LTM: Parmira is a multi-agent assistant.
STM: Focus on Memory + Terminal agents.
SYSTEM: YAML manages routing.
"""
    rag_user_prompt = rag_user_template.replace("{{user_input}}", rag_input)
    rag_out = call_model(rag_sys, rag_user_prompt)
    print("RAG Agent Input:", rag_input)
    print("RAG Agent Output:\n", rag_out)
    
    # Terminal Agent
    term_sys = cfg["terminal_prompts"]["terminal_agent"]["system_prompt"]
    term_user_template = cfg["terminal_prompts"]["terminal_agent"]["user_prompt"]
    term_input = {
        "curated_context": ["User wants a project directory structure."],
        "needed_action": "list_files",
        "path": "."
    }
    term_user_prompt = term_user_template.replace("{{rag_output}}", json.dumps(term_input, indent=2))
    term_out = call_model(term_sys, term_user_prompt)
    print("Terminal Agent Input:", term_input)
    print("Terminal Agent Output:\n", term_out)


# ==============================================================================  
# MAIN
# ==============================================================================  

def main():
    print("\n=== Loading YAML Configs ===")
    config_files = {
        "memory_prompts": CONFIG_DIR / "memory_prompts.yaml",
        "rag_prompts": CONFIG_DIR / "rag_prompts.yaml",
        "terminal_prompts": CONFIG_DIR / "terminal_prompts.yaml",
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
    test_memory_agent(configs)
    #test_rag_agent(configs)
    #test_terminal_agent(configs)
    #test_coordination(configs)

if __name__ == "__main__":
    main()


