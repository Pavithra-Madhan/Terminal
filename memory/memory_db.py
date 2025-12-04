import sqlite3
import datetime
from system.logger import memory_logger

class MemoryDB:
    def __init__(self, db_path="memory.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self._create_table()
        memory_logger.info("MemoryDB initialized.")

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()
        memory_logger.info("Memory table ensured with is_deleted column.")

    def insert_memory(self, content):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO memories (content, timestamp) VALUES (?, ?)",
                (content, datetime.datetime.now())
            )
            self.conn.commit()
            memory_logger.info(f"Inserted memory: {content[:50]}...")
        except Exception as e:
            memory_logger.error(f"Failed to insert memory: {e}")

    def fetch_all(self, include_deleted=False):
        cursor = self.conn.cursor()
        if include_deleted:
            cursor.execute("SELECT * FROM memories")
        else:
            cursor.execute("SELECT * FROM memories WHERE is_deleted=0")
        results = cursor.fetchall()
        memory_logger.info(f"Fetched {len(results)} memories (include_deleted={include_deleted})")
        return results

    def search_by_text(self, keyword):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, content, timestamp FROM memories WHERE content LIKE ? AND is_deleted=0",
            (f"%{keyword}%",)
        )
        results = cursor.fetchall()
        memory_logger.info(f"Searched for '{keyword}', found {len(results)} results.")
        return results

    def tombstone_memory(self, memory_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE memories SET is_deleted=1 WHERE id=?",
            (memory_id,)
        )
        self.conn.commit()
        memory_logger.info(f"Tombstoned memory ID {memory_id}")

    def close(self):
        self.conn.close()
        memory_logger.info("MemoryDB connection closed.")
