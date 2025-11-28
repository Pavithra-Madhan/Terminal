# run_memory_agent.py
from memory.memory_agent import MemoryAgent
from langchain.llms import HuggingFacePipeline
from transformers import pipeline

# ===========================
# Initialize Hugging Face LLM
# ===========================
hf_pipeline = pipeline(
    "text-generation",
    model="tiiuae/falcon-7b-instruct",  # or any free/small model
    max_length=256,
    temperature=0.7
)

llm = HuggingFacePipeline(pipeline=hf_pipeline)

# ===========================
# Initialize MemoryAgent
# ===========================
agent = MemoryAgent(llm)

# ===========================
# Example test interactions
# ===========================
test_inputs = [
    "Remember my favorite color is blue.",
    "What is my favorite color?",
    "Store this long-term memory: I like reading mystery novels.",
    "Search long-term memories for 'mystery novels'."
]

for user_input in test_inputs:
    output = agent.run(user_input)
    print(f"User Input: {user_input}")
    print(f"Agent Output: {output}\n")
