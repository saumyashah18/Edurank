from huggingface_hub import InferenceClient
import faiss
import numpy as np
from sqlalchemy.orm import Session
from ..database.models.chunk import Chunk, ChunkType
import os
from dotenv import load_dotenv

load_dotenv()

class Embedder:
    def __init__(self, db: Session, model_name: str = "Alibaba-NLP/gte-Qwen2-7B-instruct"):
        self.db = db
        self.model_name = model_name
        # GTE-Qwen2-7B-instruct dimension is 3584
        self.dimension = 3584 
        self.index_path = "faiss_index/index.faiss"
        self.hf_token = os.getenv("HF_TOKEN")
        
        print(f"[*] Initializing Hugging Face Embedding Client: {self.model_name}")
        self.client = InferenceClient(model=self.model_name, token=self.hf_token)
        
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
        print(f"[*] Encoding {len(texts)} chunks via Hugging Face API...")
        
        # Hugging Face Inference API
        all_embeddings = []
        for text in texts:
            try:
                emb = self.client.feature_extraction(text)
                all_embeddings.append(emb)
            except (Exception, StopIteration) as e:
                print(f"[!] Embedding Error for text: {e}")
                # Fallback to zero vector if one chunk fails
                all_embeddings.append([0.0] * self.dimension)
            
        embeddings = np.array(all_embeddings).astype('float32')
        
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
        Retrieves chunks using Hugging Face embeddings and FAISS similarity.
        """
        try:
            query_embedding = self.embedder.client.feature_extraction(query)
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

