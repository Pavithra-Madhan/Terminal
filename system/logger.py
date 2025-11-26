
import logging
from logging.handlers import RotatingFileHandler
import os

# Ensure the logs directory exists
os.makedirs("logs", exist_ok=True)

def create_logger(name: str, logfile: str, level=logging.INFO) -> logging.Logger:
    """
    Creates a logger for a specific agent.
    
    Args:
        name (str): Logger name (e.g., 'MemoryAgent')
        logfile (str): Log file path
        level: Logging level (default INFO)
        
    Returns:
        logging.Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding multiple handlers if logger already exists
    if not logger.handlers:
        handler = RotatingFileHandler(
            filename=f"logs/{logfile}",
            maxBytes=5_000_000,  # 5 MB per file
            backupCount=3         # Keep 3 backup files
        )
        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

# ===========================
# Loggers for each agent
# ===========================
memory_logger = create_logger("MemoryAgent", "memory.log")
rag_logger = create_logger("RAGAgent", "rag.log")
terminal_logger = create_logger("TerminalAgent", "terminal.log")
