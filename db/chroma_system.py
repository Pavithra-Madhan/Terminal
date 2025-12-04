import chromadb
from chromadb.config import Settings
class ChromaDB:
    def __init__(self, collection_name, persist_dir="chroma_storage"):
        self.client = chromadb.Client(
            Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=persist_dir
            )
        )
        self.collection = self.client.get_or_create_collection(collection_name)

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