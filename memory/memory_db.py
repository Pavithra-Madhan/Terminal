import sqlite3
import datetime

class MemoryDB:
    def __init__(self, db_path="memory.db"):
        # This is stored using self → it MUST persist across all methods
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)

        # This creates the table once when object is created
        self._create_table()

    def _create_table(self):
        # cursor() is temporary → NOT stored using self
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def insert_memory(self, content):
        """Store a memory in the DB."""
        cursor = self.conn.cursor()
        cursor.execute(
            '''
            INSERT INTO memories (content, timestamp)
            VALUES (?, ?)
            ''',
            (content, datetime.datetime.now())
        )
        self.conn.commit()

    def fetch_all(self):
        """Return all stored memories."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM memories")
        return cursor.fetchall()

    def search_by_text(self, keyword):
        """Simple substring search inside the content column."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, content, timestamp FROM memories WHERE content LIKE ?",
            (f"%{keyword}%",)
        )
        return cursor.fetchall()

    def close(self):
        """Close DB connection (this persists, so we do self.conn)."""
        self.conn.close()