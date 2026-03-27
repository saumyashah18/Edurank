from typing import Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..database.models.chunk import Chunk, ChunkType
import os
from dotenv import load_dotenv

load_dotenv()

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model = None

def _get_model(model_name: str = "BAAI/bge-large-en-v1.5"):
    global _model
    if _model is None:
        print(f"[*] Loading embedding model: {model_name}...")
        _model = SentenceTransformer(model_name)
        print(f"[*] Embedding model loaded successfully.")
    return _model


class Embedder:
    def __init__(self, db: Session, model_name: str = "BAAI/bge-large-en-v1.5"):
        self.db = db
        self.model_name = model_name
        self.dimension = 1024
        print(f"[*] Initializing Embedder: {self.model_name}")
        self.model = _get_model(model_name)

    def embed_chunks(self, subsection_id: int):
        """
        Embeds SMALL, MEDIUM, and LARGE chunks and stores vectors directly
        in the Chunk.embedding column in Postgres via pgvector.
        Documents are encoded WITHOUT the BGE query prefix.
        """
        print(f"\n{'-'*20} VECTORIZATION START {'-'*20}")
        # LARGE chunks embedded for broad topic retrieval (Phase 3 retrieve_broad)
        chunks = self.db.query(Chunk).filter(
            Chunk.subsection_id == subsection_id,
            Chunk.chunk_type.in_([ChunkType.SMALL, ChunkType.MEDIUM, ChunkType.LARGE])
        ).all()

        if not chunks:
            print(f"[!] No chunks found for subsection {subsection_id}")
            return

        texts = [c.content for c in chunks]
        print(f"[*] Encoding {len(texts)} chunks with {self.model_name}...")

        # Documents — no prefix, this is intentional for BGE models
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        print(f"[*] Storing {len(embeddings)} vectors in pgvector...")
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding.tolist()

        self.db.commit()
        print(f"      -> SUCCESS: {len(chunks)} vectors stored in DB")
        print(f"{'-'*20} VECTORIZATION COMPLETE {'-'*17}\n")

    def embed_query(self, query: str) -> list:
        """
        Embeds a search query WITH the BGE instruction prefix.
        Always use this for retrieval — never for document ingestion.
        """
        prefixed = BGE_QUERY_PREFIX + query
        embedding = self.model.encode(
            prefixed,
            normalize_embeddings=True
        )
        return embedding.tolist()

    def reset_index(self):
        """
        Clears all stored embeddings from the database (Postgres pgvector).
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

    def retrieve_precise(self, query: str, top_k: int = 3, course_id: Optional[int] = None):
        """
        Searches SMALL chunks by vector similarity, then returns parent chunks
        (MEDIUM) where available for broader context. Deduplicates by parent_chunk_id.
        Used by: ProfessorBot, RubricEvaluationService.
        """
        try:
            query_embedding = self.embedder.embed_query(query)
        except Exception as e:
            print(f"[!] RAG retrieve_precise Embedding Error: {e}")
            return []

        # Build optional course filter
        course_filter = "AND ch.course_id = :course_id" if course_id else ""
        params = {
            "embedding": str(query_embedding),
            "top_k": top_k,
        }
        if course_id:
            params["course_id"] = course_id

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
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """), params).fetchall()

        # Log similarity scores for the original SMALL hits
        seen_parents = set()
        output_chunks = []

        for row in results:
            chunk_id, distance = row[0], row[1]
            similarity = 1 - distance
            chunk = self.db.query(Chunk).get(chunk_id)
            if not chunk:
                continue

            print(f"[RAG] chunk_id={chunk.id} type={chunk.chunk_type.value} score={similarity:.4f} course={chunk.subsection.section.chapter.course_id if chunk.subsection else None}")

            # Small-to-big: swap to parent if available
            if chunk.parent_chunk_id:
                if chunk.parent_chunk_id in seen_parents:
                    continue  # Deduplicate: same parent already included
                seen_parents.add(chunk.parent_chunk_id)
                parent = self.db.query(Chunk).get(chunk.parent_chunk_id)
                if parent:
                    output_chunks.append(parent)
                else:
                    output_chunks.append(chunk)  # Fallback if parent missing
            else:
                output_chunks.append(chunk)

        return output_chunks

    # ------------------------------------------------------------------
    #  BROAD RETRIEVAL (LARGE chunks for topic/section selection)
    # ------------------------------------------------------------------

    def retrieve_broad(self, query: str, top_k: int = 5, course_id: Optional[int] = None):
        """
        Searches LARGE chunks for broad topic matching.
        Used by: TopicPlanner for section/topic selection.
        """
        try:
            query_embedding = self.embedder.embed_query(query)
        except Exception as e:
            print(f"[!] RAG retrieve_broad Embedding Error: {e}")
            return []

        course_filter = "AND ch.course_id = :course_id" if course_id else ""
        params = {
            "embedding": str(query_embedding),
            "top_k": top_k,
        }
        if course_id:
            params["course_id"] = course_id

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
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """), params).fetchall()

        chunks = []
        for row in results:
            chunk_id, distance = row[0], row[1]
            similarity = 1 - distance
            chunk = self.db.query(Chunk).get(chunk_id)
            if chunk:
                print(f"[RAG] chunk_id={chunk.id} type={chunk.chunk_type.value} score={similarity:.4f} course={chunk.subsection.section.chapter.course_id if chunk.subsection else None}")
                chunks.append(chunk)

        return chunks

    # ------------------------------------------------------------------
    #  LEGACY / GENERIC RETRIEVAL (backward compatible)
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 3, chunk_types: Optional[list] = None, course_id: Optional[int] = None):
        """
        Generic retrieval method — preserved for backward compatibility.
        Supports optional chunk_type and course_id filters.
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
        params = {
            "embedding": str(query_embedding),
            "top_k": top_k,
        }
        if course_id:
            params["course_id"] = course_id

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
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """), params).fetchall()

        chunks = []
        for row in results:
            chunk_id, distance = row[0], row[1]
            similarity = 1 - distance
            chunk = self.db.query(Chunk).get(chunk_id)
            if chunk:
                print(f"[RAG] chunk_id={chunk.id} type={chunk.chunk_type.value} score={similarity:.4f} course={chunk.subsection.section.chapter.course_id if chunk.subsection else None}")
                chunks.append(chunk)

        return chunks


def test_prefix_improvement():
    """
    Run this to verify the prefix improves retrieval scores.
    Usage: python -c "from backend.rag.embedder import test_prefix_improvement; test_prefix_improvement()"
    """
    from sentence_transformers import util

    model = SentenceTransformer("BAAI/bge-large-en-v1.5")
    prefix = BGE_QUERY_PREFIX

    question = "What are the phases of mitosis?"
    chunk = (
        "Mitosis consists of four phases: prophase, metaphase, anaphase, "
        "and telophase. Each phase has distinct characteristics..."
    )

    q_no_prefix  = model.encode(question,           normalize_embeddings=True)
    q_with_prefix = model.encode(prefix + question,  normalize_embeddings=True)
    doc           = model.encode(chunk,              normalize_embeddings=True)

    score_before = util.cos_sim(q_no_prefix,  doc).item()
    score_after  = util.cos_sim(q_with_prefix, doc).item()

    print(f"Score WITHOUT prefix: {score_before:.4f}")
    print(f"Score WITH prefix:    {score_after:.4f}")
    print(f"Improvement:          +{score_after - score_before:.4f}")
    assert score_after > score_before, "Prefix should improve similarity score"
    print("Test passed.")
