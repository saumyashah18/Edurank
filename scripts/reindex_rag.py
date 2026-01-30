import os
import sys
import numpy as np
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database.session import SessionLocal
from backend.database.models.chunk import Chunk, ChunkType
from backend.rag.embedder import Embedder

def reindex_all_chunks():
    db = SessionLocal()
    try:
        print("[*] Starting Re-indexing Process...")
        embedder = Embedder(db)
        
        # Reset FAISS index
        embedder.reset_index()
        
        # Fetch all SMALL and MEDIUM chunks
        chunks = db.query(Chunk).filter(
            Chunk.chunk_type.in_([ChunkType.SMALL, ChunkType.MEDIUM])
        ).order_by(Chunk.id).all()
        
        if not chunks:
            print("[!] No chunks found in database.")
            return

        print(f"[*] Found {len(chunks)} chunks to re-index.")
        
        # Process in batches to avoid API timeouts
        batch_size = 30
        all_embeddings = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.content for c in batch]
            print(f"[*] Processing batch {i//batch_size + 1} ({len(batch)} chunks)...")
            
            batch_embeddings = []
            for text in texts:
                try:
                    emb = embedder.client.feature_extraction(text)
                    batch_embeddings.append(emb)
                except Exception as e:
                    print(f"[!] Embedding Error: {e}")
                    batch_embeddings.append([0.0] * embedder.dimension)
            
            all_embeddings.extend(batch_embeddings)
            
        embeddings_np = np.array(all_embeddings).astype('float32')
        
        # Add to FAISS and map IDs
        print(f"[*] Syncing {len(embeddings_np)} vectors to FAISS...")
        embedder.index.add(embeddings_np)
        
        for idx, chunk in enumerate(chunks):
            chunk.vector_id = str(idx)
        
        db.commit()
        embedder._save_index()
        
        print(f"\n[+] SUCCESS: Re-indexed {len(chunks)} chunks.")
        print(f"[+] Final FAISS Index contains {embedder.index.ntotal} vectors.")
        
    except Exception as e:
        print(f"[!] Re-indexing Failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reindex_all_chunks()
