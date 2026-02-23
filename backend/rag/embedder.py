from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from sqlalchemy.orm import Session
from ..database.models.chunk import Chunk, ChunkType
import os
from dotenv import load_dotenv

load_dotenv()

# Global model instance (loaded once, reused across requests)
_model = None

def _get_model(model_name: str = "BAAI/bge-large-en-v1.5"):
    global _model
    if _model is None:
        print(f"[*] Loading local embedding model: {model_name} (first load downloads ~1.3GB)...")
        _model = SentenceTransformer(model_name)
        print(f"[*] Embedding model loaded successfully.")
    return _model


class Embedder:
    def __init__(self, db: Session, model_name: str = "BAAI/bge-large-en-v1.5"):
        self.db = db
        self.model_name = model_name
        # BGE-Large-en-v1.5 dimension is 1024
        self.dimension = 1024 
        self.index_path = "faiss_index/index.faiss"
        
        print(f"[*] Initializing Local Embedding Model: {self.model_name}")
        self.model = _get_model(model_name)
        
        if os.path.exists(self.index_path):
            try:
                self.index = faiss.read_index(self.index_path)
                if self.index.d != self.dimension:
                    print(f"[!] FAISS Dimension Mismatch ({self.index.d} vs {self.dimension}). Re-initializing index.")
                    self.index = faiss.IndexFlatL2(self.dimension)
            except Exception:
                self.index = faiss.IndexFlatL2(self.dimension)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)

    def embed_chunks(self, subsection_id: int):
        """
        Embeds chunks locally using SentenceTransformers (Free & Unlimited).
        """
        print(f"\n{'-'*20} LOCAL VECTORIZATION START {'-'*20}")
        chunks = self.db.query(Chunk).filter(
            Chunk.subsection_id == subsection_id,
            Chunk.chunk_type.in_([ChunkType.SMALL, ChunkType.MEDIUM])
        ).all()

        if not chunks:
            print(f"[!] No chunks found to embed for subsection {subsection_id}")
            return

        texts = [c.content for c in chunks]
        print(f"[*] Encoding {len(texts)} chunks locally with {self.model_name}...")
        
        # Local embedding — no API calls, no rate limits
        embeddings = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        embeddings = np.array(embeddings).astype('float32')
        
        # Add to FAISS and map IDs
        print(f"[*] Syncing {len(embeddings)} vectors to FAISS...")
        start_idx = self.index.ntotal
        self.index.add(embeddings)
        
        for i, chunk in enumerate(chunks):
            chunk.vector_id = str(start_idx + i)
        
        self.db.commit()
        print(f"      -> SUCCESS: Sub-total indexed vectors: {self.index.ntotal}")
        print(f"{'-'*20} LOCAL VECTORIZATION COMPLETE {'-'*17}\n")

        self._save_index()

    def _save_index(self):
        if not os.path.exists("faiss_index"):
            os.makedirs("faiss_index" )
        faiss.write_index(self.index, self.index_path)

    def reset_index(self):
        """Wipes the FAISS index and deletes the disk cache."""
        print("[*] Resetting FAISS Vector Index...")
        self.index = faiss.IndexFlatL2(self.dimension)
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        print("    -> FAISS Index Cleared.")

class RAGService:
    def __init__(self, db: Session, embedder: Embedder):
        self.db = db
        self.embedder = embedder

    def retrieve(self, query: str, top_k: int = 3, chunk_types: list = None):
        """
        Retrieves chunks using local embeddings and FAISS similarity.
        """
        try:
            query_embedding = self.embedder.model.encode([query], normalize_embeddings=True)
            query_embedding = np.array(query_embedding).astype('float32').reshape(1, -1)
        except (Exception, StopIteration) as e:
            print(f"[!] RAG Retrieval Embedding Error: {e}")
            return []
        
        distances, indices = self.embedder.index.search(query_embedding, top_k)
        
        results = []
        for idx in indices[0]:
            if idx == -1: continue
            chunk = self.db.query(Chunk).filter_by(vector_id=str(idx)).first()
            if chunk:
                if chunk_types and chunk.chunk_type not in chunk_types:
                    continue
                results.append(chunk)
        
        return results
