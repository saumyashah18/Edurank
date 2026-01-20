from typing import List
from sqlalchemy.orm import Session
from ..database.models.chunk import Chunk, ChunkType
from ..database.models.hierarchy import Subsection, RawMaterial
from ..quiz.llm_service import llm

class Chunker:
    def __init__(self, db: Session):
        self.db = db
        self.llm = llm




    def generate_chunks(self, subsection_id: int):
        """
        Refined sequence:
        1. Hierarchy exists (Subsection -> RawMaterial).
        2. Paragraph splitting.
        3. Semantic refinement (merging).
        4. S, M, L derivation.
        """
        print(f"\n{'='*20} CHUNKING START (Subsection: {subsection_id}) {'='*20}")
        raw_material = self.db.query(RawMaterial).filter_by(subsection_id=subsection_id).first()
        if not raw_material:
            print(f"[ERROR] No raw material found for subsection {subsection_id}")
            return

        # Step 2: Paragraph Chunking
        print(f"[1/3] Splitting raw text into paragraphs...")
        paragraphs = self._split_into_paragraphs(raw_material.content)
        print(f"      -> SUCCESS: Found {len(paragraphs)} logical paragraphs (S chunks)")
        
        # Step 3: Semantic Refinement (Merging)
        print(f"[2/3] Applying Semantic Merger (AI-Logic)...")
        refined_paragraphs = self._semantic_merge(paragraphs)
        print(f"      -> SUCCESS: Refined into {len(refined_paragraphs)} meaningful explanations (M chunks)")
        
        # Step 4: Multi-Granularity Derivation
        print(f"[3/3] Committing Multi-Granularity Index (S, M, L) to DB...")
        # Small (S) = Individual (unmerged) paragraphs
        self._create_chunks(subsection_id, paragraphs, ChunkType.SMALL)
        
        # Medium (M) = Refined (merged) paragraphs
        self._create_chunks(subsection_id, refined_paragraphs, ChunkType.MEDIUM)
        
        # Large (L) = Concept scope (Full text)
        self._create_l_chunk(subsection_id, raw_material.content)
        
        self.db.commit()
        print(f"{'='*20} CHUNKING COMPLETE {'='*24}\n")



    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Splits text into paragraphs based on double newlines."""
        return [p.strip() for p in text.split('\n\n') if p.strip()]

    def _semantic_merge(self, paragraphs: List[str]) -> List[str]:
        """
        Uses an LLM or logic to merge semantically related paragraphs.
        For now, implementing a logic-based merge skeleton.
        """
        if len(paragraphs) <= 1:
            return paragraphs
            
        merged = []
        i = 0
        while i < len(paragraphs):
            current = paragraphs[i]
            if i + 1 < len(paragraphs):
                next_p = paragraphs[i+1]
                # Placeholder for semantic check: if next_p starts with lowercase or 
                # a conjunction, or if LLM says they should merge.
                if self._should_merge(current, next_p):
                    merged.append(current + " " + next_p)
                    i += 2
                    continue
            merged.append(current)
            i += 1
        return merged

    def _should_merge(self, p1: str, p2: str) -> bool:
        """
        Logic for semantic completeness check.
        Can be enhanced with LLM or NLP.
        """
        # Basic heuristic: merge if p2 starts with a lower case 
        # or if p1 is very short (less than 100 chars).
        if len(p1) < 100 or (p2 and p2[0].islower()):
            return True
        return False

    def _create_chunks(self, subsection_id: int, text_list: List[str], chunk_type: ChunkType):
        for text in text_list:
            chunk = Chunk(
                content=text,
                chunk_type=chunk_type,
                subsection_id=subsection_id
            )
            self.db.add(chunk)

    def _create_l_chunk(self, subsection_id: int, full_text: str):
        chunk = Chunk(
            content=full_text,
            chunk_type=ChunkType.LARGE,
            subsection_id=subsection_id
        )
        self.db.add(chunk)
