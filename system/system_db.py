"""
system_indexer.py

Unified system indexer:
- Builds/updates a SQLite "files" table as a truth snapshot (deletes removed files)
- Appends file metadata to Chroma as an append-only semantic history
- Optional embedder integration (embedder.embed(text) -> list[float])
- Optional scheduler support (reindex periodically)
- Safe scanning with progress bar and permission handling

Usage:
    from system_indexer import SystemIndexer
    idx = SystemIndexer(root_paths=["C:\\Users\\Pavi"], db_path="system.db",
                        chroma_enabled=True, chroma_collection_name="system_files",
                        embedder=my_embedder)
    idx.index_system()
    idx.close()

Notes:
 - For Chroma embedding: pass an embedder object with .embed(text) -> list[float].
 - If chromadb isn't installed or chroma_enabled=False, Chroma steps are skipped.
"""

import os
import sqlite3
import time
import logging
from datetime import datetime
from tqdm import tqdm
from typing import List, Optional

# Optional chroma import
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMA = True
except Exception:
    HAS_CHROMA = False

# Optional schedule import (for periodic reindex)
try:
    import schedule
    HAS_SCHEDULE = True
except Exception:
    HAS_SCHEDULE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class SystemIndexer:
    def __init__(
        self,
        root_paths: List[str],
        db_path: str = "system.db",
        chroma_enabled: bool = False,
        chroma_collection_name: str = "system_files",
        embedder: Optional[object] = None,
        skip_extensions: Optional[List[str]] = None,
    ):
        """
        root_paths: list of directories to scan (e.g. ["C:\\Users\\Pavi"])
        db_path: sqlite db path
        chroma_enabled: whether to append to chroma (requires chromadb installed)
        embedder: optional object with .embed(text)->list[float] for embeddings
        skip_extensions: optional list of file extensions to skip (like [".sys", ".dll"])
        """

        self.root_paths = root_paths
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.execute("PRAGMA journal_mode=WAL;")  # more robust concurrency
        self._create_tables()

        self.embedder = embedder
        self.skip_extensions = set((e.lower() for e in (skip_extensions or [])))

        # Chroma setup (optional)
        self.chroma_enabled = chroma_enabled and HAS_CHROMA
        if chroma_enabled and not HAS_CHROMA:
            logging.warning("chroma_enabled=True but chromadb is not installed. Chroma will be disabled.")
            self.chroma_enabled = False

        if self.chroma_enabled:
            # Persist directory default: ./chroma_store
            self.chroma_client = chromadb.Client(
                Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory="chroma_store"
                )
            )
            self.collection = self.chroma_client.get_or_create_collection(name=chroma_collection_name)
            logging.info("Chroma collection ready: %s", chroma_collection_name)

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE,
                name TEXT,
                extension TEXT,
                size INTEGER,
                last_modified TIMESTAMP,
                last_seen TIMESTAMP
            )
        """)
        # index on name to speed up substring search
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_name ON files(name)")
        self.conn.commit()

    def _is_extension_skipped(self, filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.skip_extensions

    def index_system(self, batch_size: int = 500):
        """
        Perform a full system index:
        - Walk the given root_paths
        - Update/insert each file row with last_seen = now
        - After scanning, delete rows whose last_seen < scan_start (they were removed)
        - Append entries to Chroma (append-only) with ID = f"{path}::{timestamp}"
        """

        scan_start = datetime.utcnow()
        scan_iso = scan_start.isoformat()
        logging.info("Starting full index at %s", scan_iso)

        # Collect all files first (to give progress bar)
        all_files = []
        for root in self.root_paths:
            # normalize root path
            root = os.path.expanduser(root)
            if not os.path.exists(root):
                logging.warning("Root path does not exist, skipping: %s", root)
                continue
            for dirpath, _, filenames in os.walk(root):
                for fname in filenames:
                    full_path = os.path.join(dirpath, fname)
                    all_files.append(full_path)

        total = len(all_files)
        logging.info("Discovered %d files to process", total)

        cur = self.conn.cursor()

        # We'll update last_seen to the scan timestamp for found files
        now_ts = datetime.utcnow()

        # Process files with tqdm
        for i in tqdm(range(total), desc="Indexing files", ncols=100):
            full_path = all_files[i]
            try:
                stat = os.stat(full_path)
            except Exception:
                # Skip unreadable files (permissions, symlink loops etc.)
                continue

            name = os.path.basename(full_path)
            if self._is_extension_skipped(name):
                continue

            ext = os.path.splitext(name)[1]
            size = stat.st_size
            last_mod = datetime.fromtimestamp(stat.st_mtime)

            # Insert or replace with updated data and last_seen
            cur.execute(
                """
                INSERT INTO files (path, name, extension, size, last_modified, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    name=excluded.name,
                    extension=excluded.extension,
                    size=excluded.size,
                    last_modified=excluded.last_modified,
                    last_seen=excluded.last_seen
                """,
                (full_path, name, ext, size, last_mod, now_ts)
            )

            # Chroma append-only: create a unique id per entry so history is preserved.
            if self.chroma_enabled:
                try:
                    # Compose a stable-ish doc id that is unique per index event
                    chroma_id = f"{full_path}::{int(time.time()*1000)}"
                    doc_text = name  # minimal: just filename; extend to file preview if desired
                    metadata = {"path": full_path, "extension": ext, "last_modified": last_mod.isoformat()}

                    # If embedder provided, embed and add with embeddings
                    if self.embedder is not None and hasattr(self.embedder, "embed"):
                        emb = self.embedder.embed(doc_text)
                        # ensure emb is a list of floats
                        self.collection.add(
                            ids=[chroma_id],
                            documents=[doc_text],
                            embeddings=[emb],
                            metadatas=[metadata]
                        )
                    else:
                        # add document + metadata, let Chroma handle embeddings (if configured)
                        self.collection.add(
                            ids=[chroma_id],
                            documents=[doc_text],
                            metadatas=[metadata]
                        )
                except Exception as e:
                    # Chroma shouldn't stop the indexer; log and continue
                    logging.warning("Chroma add failed for %s: %s", full_path, e)

        self.conn.commit()

        # Remove rows that were not seen in this scan (they were deleted/moved)
        try:
            cur.execute(
                "DELETE FROM files WHERE last_seen < ?",
                (now_ts,)
            )
            deleted_count = cur.rowcount
            if deleted_count:
                logging.info("Removed %d files from SQLite that were not present this scan", deleted_count)
            self.conn.commit()
        except Exception as e:
            logging.warning("Failed to cleanup removed files: %s", e)

        logging.info("Indexing finished at %s", datetime.utcnow().isoformat())

    def search_sqlite_by_name(self, query: str, limit: int = 50):
        """Simple substring search in filename (case-insensitive)."""
        cur = self.conn.cursor()
        like_q = f"%{query}%"
        cur.execute("SELECT path, name, extension, size, last_modified FROM files WHERE name LIKE ? LIMIT ?",
                    (like_q, limit))
        return cur.fetchall()

    def list_recent_files(self, limit: int = 50):
        cur = self.conn.cursor()
        cur.execute("SELECT path, name, extension, size, last_modified FROM files ORDER BY last_modified DESC LIMIT ?",
                    (limit,))
        return cur.fetchall()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


# ---- Optional scheduler helpers ----

def start_periodic_indexer(indexer: SystemIndexer, every_minutes: int = 60):
    """
    Start a periodic indexer if `schedule` is available.
    This function will block calling schedule.run_pending() in a loop.
    Use in a background process if you don't want blocking behavior.
    """
    if not HAS_SCHEDULE:
        raise RuntimeError("Install 'schedule' package to use periodic scheduling: pip install schedule")

    schedule.clear()
    schedule.every(every_minutes).minutes.do(indexer.index_system)
    logging.info("Scheduled periodic indexing every %d minutes.", every_minutes)
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Scheduler stopped.")


# ---- Simple CLI example ----
if __name__ == "__main__":
    # Basic usage: edit the root_paths below or pass via environment
    roots = [
        os.path.expanduser("~/"),  # safe default: user home
    ]

    idx = SystemIndexer(
        root_paths=roots,
        db_path="system.db",
        chroma_enabled=False,      # set True if you installed chromadb
        chroma_collection_name="system_files",
        embedder=None,             # optionally pass an embedder object with .embed()
        skip_extensions=[".sys", ".dll", ".lnk"]  # skip common binary/sys extensions if desired
    )

    # quick one-shot index
    idx.index_system()

    # if you want to run periodic indexing (uncomment to use)
    # start_periodic_indexer(idx, every_minutes=60)

    idx.close()
