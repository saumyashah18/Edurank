from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import os
from sqlalchemy.orm import Session
from ..database.models.chunk import Chunk, ChunkType

class Embedder:
    def __init__(self, db: Session, model_name: str = "all-MiniLM-L6-v2"):
        self.db = db
        self.model_name = model_name
        # all-MiniLM-L6-v2 dimension is 384. Previous Gemini was 768.
        self.dimension = 384 
        self.index_path = "faiss_index/index.faiss"
        
        print(f"[*] Initializing Local Embedding Model: {self.model_name}")
        self.model = SentenceTransformer(model_name)
        
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
        print(f"[*] Encoding {len(texts)} chunks locally...")
        
        # Local inference (Free!)
        embeddings = self.model.encode(texts)
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
            os.makedirs("faiss_index")
        faiss.write_index(self.index, self.index_path)

class RAGService:
    def __init__(self, db: Session, embedder: Embedder):
        self.db = db
        self.embedder = embedder

    def retrieve(self, query: str, top_k: int = 3, chunk_types: list = None):
        """
        Retrieves chunks locally based on query similarity.
        """
        query_embedding = self.embedder.model.encode([query])
        query_embedding = np.array(query_embedding).astype('float32').reshape(1, -1)
        
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

