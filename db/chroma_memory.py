import chromadb
from chromadb.config import Settings

class ChromaMemory:
    def __init__(self, persist_dir="chroma_storage"):
        self.client = chromadb.Client(
            Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=persist_dir
            )
        )

        self.collection = self.client.get_or_create_collection(
            name="semantic_memory"
        )

    def add(self, memory_id, text, embedding):
        self.collection.add(
            ids=[str(memory_id)],
            documents=[text],
            embeddings=[embedding]
        )

    def query(self, embedding, top_k=5):
        return self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k
        )
