from sentence_transformers import SentenceTransformer

class Embedder:
    def __init__(self, model_name = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
    def embed(self, text: str) -> list:
        """Generate embedding for the given text."""
        embeddings = self.model.encode(text)
        return embeddings.tolist()
    
if __name__ == "__main__":
    e = Embedder()
    print(len(e.embed("Hello, world!"))) 