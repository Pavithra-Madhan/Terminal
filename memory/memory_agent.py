# memory_agent.py
import yaml
from langchain.agents import initialize_agent, Tool
from langchain.llms import HuggingFacePipeline
from .memory import (
    store_memory,
    tombstone_memory,
    search_memory,
    fetch_all_memories,
    store_ltm_memory,
    search_ltm_memory
)
from system.logger import memory_logger

class MemoryAgent:
    def __init__(self, hf_pipeline: HuggingFacePipeline):
        """
        MemoryAgent using Hugging Face model.
        
        Args:
            hf_pipeline (HuggingFacePipeline): A Hugging Face LLM wrapped for LangChain.
        """
        self.llm = hf_pipeline

        with open(yaml_path, "r") as f:
            self.memory_config = yaml.safe_load(f)
            memory_logger.info("Memory YAML config loaded.")

        # Wrap memory tools for LangChain agent
        self.tools = [
            Tool(name="store_memory", func=store_memory, description="Store a short-term memory."),
            Tool(name="tombstone_memory", func=tombstone_memory, description="Tombstone (soft-delete) a memory by ID."),
            Tool(name="search_memory", func=search_memory, description="Search STM memories by keyword."),
            Tool(name="fetch_all_memories", func=fetch_all_memories, description="Fetch all STM memories."),
            Tool(name="store_ltm_memory", func=store_ltm_memory, description="Store a long-term memory in Chroma."),
            Tool(name="search_ltm_memory", func=search_ltm_memory, description="Search long-term memories in Chroma."),
        ]

        # Initialize LangChain zero-shot agent
        self.agent = AgentExecutor.from_agent_and_tools(
            agent=self.llm,  # this will be wrapped appropriately
            tools=self.tools,
            verbose=True
        )

        memory_logger.info("MemoryAgent initialized with Hugging Face LLM.")

    def run(self, user_input: str):
        """Send input to the agent and execute relevant memory tools."""
        memory_logger.info(f"MemoryAgent received input: {user_input[:50]}")
        result = self.agent.run(user_input)
        memory_logger.info(f"MemoryAgent output: {str(result)[:100]}")
        return result
