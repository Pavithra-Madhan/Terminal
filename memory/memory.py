from .memory_db import MemoryDB
from db.chroma_memory import ChromaMemory
from system.logger import memory_logger
from langchain.tools import tool 

# ===========================
# Instantiate MemoryDB once for agent use
# ===========================
memory_db = MemoryDB()
chroma_db = ChromaMemory()

# ===========================
# LLM-callable tools
# ===========================

@tool("store_memory")
def store_memory(content: str):
    """Store a new memory in STM (short-term memory)."""
    memory_db.insert_memory(content)
    memory_logger.info(f"Stored memory: {content[:50]}")
    return f"Memory stored: {content[:50]}..."

@tool("tombstone_memory")
def tombstone_memory(memory_id: int):
    """Soft-delete a memory by ID (tombstoning)."""
    memory_db.tombstone_memory(memory_id)
    memory_logger.info(f"Tombstoned memory ID {memory_id}")
    return f"Tombstoned memory ID {memory_id}"

@tool("search_memory")
def search_memory(keyword: str):
    """Search STM for a keyword."""
    results = memory_db.search_by_text(keyword)
    memory_logger.info(f"Searched for '{keyword}', found {len(results)} results")
    return results

@tool("fetch_all_memories")
def fetch_all_memories():
    """Return all stored memories."""
    results = memory_db.fetch_all()
    memory_logger.info(f"Fetched all memories, total {len(results)}")
    return results

# ===========================
# LTM (Chroma) tools
# ===========================

@tool("store_ltm_memory")
def store_ltm_memory(content: str):
    chroma_db.add(content)
    memory_logger.info(f"Stored LTM memory: {content[:50]}")
    return f"LTM memory stored: {content[:50]}..."

@tool("search_ltm_memory")
def search_ltm_memory(query: str):
    results = chroma_db.query(query)
    memory_logger.info(f"Searched LTM for '{query}', found {len(results)} results")
    return results

# ===========================
# Optional: cleanup (internal)
# ===========================

def close_memory():
    """Close DB connection (internal use)."""
    memory_db.close()
    memory_logger.info("MemoryDB connection closed.")
