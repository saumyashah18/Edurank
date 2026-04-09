import os
import requests
import numpy as np
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from dotenv import load_dotenv
from ..database.models.chunk import Chunk, ChunkType

load_dotenv()

# Prefix for better Llama/BGE-like retrieval performance
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

class Embedder:
    def __init__(self, db: Session, model_name: str = None):
        self.db = db
        # Prioritize ENV, then passed arg, then default
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.dimension = 4096  # Llama 3.1 8B default dimension
        print(f"[*] Initializing Ollama Embedder: {self.ollama_url} | Model: {self.model_name}")

    def _call_ollama_embed(self, text: str) -> list:
        """Calls Ollama's embedding API for a single text string."""
        url = f"{self.ollama_url}/api/embeddings"
        payload = {
            "model": self.model_name,
            "prompt": text
        }
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            return response.json().get("embedding", [])
        except Exception as e:
            print(f"[!] Ollama Embedding Error: {e}")
            # Return zero vector if it fails to avoid breaking RAG completely
            return [0.0] * self.dimension

    def embed_chunks(self, subsection_id: int):
        """
        Embeds SMALL, MEDIUM, and LARGE chunks via Ollama and stores vectors
        in Postgres via pgvector.
        """
        print(f"\n{'-'*20} VECTORIZATION START (OLLAMA) {'-'*20}")
        chunks = self.db.query(Chunk).filter(
            Chunk.subsection_id == subsection_id,
            Chunk.chunk_type.in_([ChunkType.SMALL, ChunkType.MEDIUM, ChunkType.LARGE])
        ).all()

        if not chunks:
            print(f"[!] No chunks found for subsection {subsection_id}")
            return

        print(f"[*] Encoding {len(chunks)} chunks with Ollama ({self.model_name})...")

        count = 0
        for chunk in chunks:
            # We embed one by one since Ollama's batch embedding support varies by version
            embedding = self._call_ollama_embed(chunk.content)
            if embedding and len(embedding) == self.dimension:
                chunk.embedding = embedding
                count += 1
            
            if count % 10 == 0 and count > 0:
                print(f"    -> Progress: {count}/{len(chunks)} chunks embedded")

        self.db.commit()
        print(f"      -> SUCCESS: {count} vectors stored in DB")
        print(f"{'-'*20} VECTORIZATION COMPLETE {'-'*17}\n")

    def embed_query(self, query: str) -> list:
        """
        Embeds a search query with an instruction prefix for better retrieval performance.
        """
        prefixed = BGE_QUERY_PREFIX + query
        return self._call_ollama_embed(prefixed)

    def reset_index(self):
        """
        Clears all stored embeddings from the database.
        """
        print("[*] Resetting all stored embeddings...")
        self.db.query(Chunk).update({"embedding": None})
        self.db.commit()
        print("    -> All embeddings cleared.")


class RAGService:
    def __init__(self, db: Session, embedder: Embedder):
        self.db = db
        self.embedder = embedder

    # ------------------------------------------------------------------
    #  PRECISE RETRIEVAL (Small-to-Big)
    # ------------------------------------------------------------------

    def retrieve_precise(self, query: str, top_k: int = 3, course_id: Optional[int] = None, selected_document_ids: Optional[list] = None):
        """
        Searches SMALL chunks by vector similarity, then returns parent chunks
        (MEDIUM) where available for broader context. Deduplicates by parent_chunk_id.
        Used by: ProfessorBot, Rubric Evaluation Service.
        """
        try:
            query_embedding = self.embedder.embed_query(query)
        except Exception as e:
            print(f"[!] RAG retrieve_precise Embedding Error: {e}")
            return []

        # Build optional filters
        course_filter = "AND ch.course_id = :course_id" if course_id else ""
        doc_filter = "AND doc.id IN :doc_ids" if selected_document_ids else ""
        
        params = {
            "embedding": str(query_embedding),
            "top_k": top_k,
        }
        if course_id:
            params["course_id"] = course_id
        if selected_document_ids:
            params["doc_ids"] = tuple(selected_document_ids)

        results = self.db.execute(text(f"""
            SELECT c.id, (c.embedding <=> CAST(:embedding AS vector)) AS distance
            FROM chunks c
            LEFT JOIN subsections sub ON c.subsection_id = sub.id
            LEFT JOIN sections sec ON sub.section_id = sec.id
            LEFT JOIN chapters ch ON sec.chapter_id = ch.id
            LEFT JOIN documents doc ON c.document_id = doc.id
            WHERE c.embedding IS NOT NULL
            AND c.chunk_type = 'SMALL'
            AND (doc.ingestion_status IN ('COMPLETED', 'CONCEPT_EXTRACTION', 'FULLY_READY') OR doc.id IS NULL)
            {course_filter}
            {doc_filter}
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """), params).fetchall()

        seen_parents = set()
        output_chunks = []

        for row in results:
            chunk_id, distance = row[0], row[1]
            similarity = 1 - distance
            chunk = self.db.query(Chunk).get(chunk_id)
            if not chunk:
                continue

            print(f"[RAG] chunk_id={chunk.id} type={chunk.chunk_type.name} score={similarity:.4f}")

            # Small-to-big: swap to parent if available
            if chunk.parent_chunk_id:
                if chunk.parent_chunk_id in seen_parents:
                    continue  # Deduplicate
                seen_parents.add(chunk.parent_chunk_id)
                parent = self.db.query(Chunk).get(chunk.parent_chunk_id)
                if parent:
                    output_chunks.append(parent)
                else:
                    output_chunks.append(chunk)
            else:
                output_chunks.append(chunk)

        return output_chunks

    # ------------------------------------------------------------------
    #  BROAD RETRIEVAL (LARGE chunks for topic/section selection)
    # ------------------------------------------------------------------

    def retrieve_broad(self, query: str, top_k: int = 5, course_id: Optional[int] = None, selected_document_ids: Optional[list] = None):
        """
        Searches LARGE chunks for broad topic matching.
        """
        try:
            query_embedding = self.embedder.embed_query(query)
        except Exception as e:
            print(f"[!] RAG retrieve_broad Embedding Error: {e}")
            return []

        course_filter = "AND ch.course_id = :course_id" if course_id else ""
        doc_filter = "AND doc.id IN :doc_ids" if selected_document_ids else ""
        
        params = {
            "embedding": str(query_embedding),
            "top_k": top_k,
        }
        if course_id:
            params["course_id"] = course_id
        if selected_document_ids:
            params["doc_ids"] = tuple(selected_document_ids)

        results = self.db.execute(text(f"""
            SELECT c.id, (c.embedding <=> CAST(:embedding AS vector)) AS distance
            FROM chunks c
            LEFT JOIN subsections sub ON c.subsection_id = sub.id
            LEFT JOIN sections sec ON sub.section_id = sec.id
            LEFT JOIN chapters ch ON sec.chapter_id = ch.id
            LEFT JOIN documents doc ON c.document_id = doc.id
            WHERE c.embedding IS NOT NULL
            AND c.chunk_type = 'LARGE'
            AND (doc.ingestion_status IN ('COMPLETED', 'CONCEPT_EXTRACTION', 'FULLY_READY') OR doc.id IS NULL)
            {course_filter}
            {doc_filter}
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """), params).fetchall()

        chunks = []
        for row in results:
            chunk_id, distance = row[0], row[1]
            similarity = 1 - distance
            chunk = self.db.query(Chunk).get(chunk_id)
            if chunk:
                print(f"[RAG] chunk_id={chunk.id} type={chunk.chunk_type.name} score={similarity:.4f}")
                chunks.append(chunk)

        return chunks

    # ------------------------------------------------------------------
    #  LEGACY / GENERIC RETRIEVAL
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 3, chunk_types: Optional[List[ChunkType]] = None, course_id: Optional[int] = None, selected_document_ids: Optional[list] = None):
        """
        Generic retrieval method preserve for backward compatibility.
        """
        try:
            query_embedding = self.embedder.embed_query(query)
        except Exception as e:
            print(f"[!] RAG Retrieval Embedding Error: {e}")
            return []

        # Build filters
        type_filter = ""
        if chunk_types:
            type_names = [f"'{ct.name}'" for ct in chunk_types]
            type_filter = f"AND c.chunk_type IN ({','.join(type_names)})"

        course_filter = "AND ch.course_id = :course_id" if course_id else ""
        doc_filter = "AND doc.id IN :doc_ids" if selected_document_ids else ""
        
        params = {
            "embedding": str(query_embedding),
            "top_k": top_k,
        }
        if course_id:
            params["course_id"] = course_id
        if selected_document_ids:
            params["doc_ids"] = tuple(selected_document_ids)

        results = self.db.execute(text(f"""
            SELECT c.id, (c.embedding <=> CAST(:embedding AS vector)) AS distance
            FROM chunks c
            LEFT JOIN subsections sub ON c.subsection_id = sub.id
            LEFT JOIN sections sec ON sub.section_id = sec.id
            LEFT JOIN chapters ch ON sec.chapter_id = ch.id
            LEFT JOIN documents doc ON c.document_id = doc.id
            WHERE c.embedding IS NOT NULL
            AND (doc.ingestion_status IN ('COMPLETED', 'CONCEPT_EXTRACTION', 'FULLY_READY') OR doc.id IS NULL)
            {type_filter}
            {course_filter}
            {doc_filter}
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """), params).fetchall()

        chunks = []
        for row in results:
            chunk_id, distance = row[0], row[1]
            similarity = 1 - distance
            chunk = self.db.query(Chunk).get(chunk_id)
            if chunk:
                print(f"[RAG] chunk_id={chunk.id} type={chunk.chunk_type.name} score={similarity:.4f}")
                chunks.append(chunk)

        return chunks
