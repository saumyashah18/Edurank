import re
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from ..database.models.chunk import Chunk, ChunkType
from ..database.models.hierarchy import Subsection, RawMaterial
import tiktoken

# Token counting with cl100k_base (GPT-4 / BGE compatible)
enc = tiktoken.get_encoding("cl100k_base")
MAX_CHUNK_TOKENS = 400  # BGE hard limit is 512; we target 400 for safety

CONTINUATION_SIGNALS = [
    "however", "therefore", "furthermore", "additionally", "moreover",
    "thus", "hence", "consequently", "in addition", "as a result",
    "for example", "for instance", "in contrast", "on the other hand",
    "similarly", "likewise",
]

OVERLAP_MARKER = "\n\n[OVERLAP]\n\n"


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken cl100k_base encoding."""
    return len(enc.encode(text))


def _is_heading(text: str) -> bool:
    """Detect headings: markdown-style, ALL CAPS short lines, or short lines without punctuation."""
    stripped = text.strip()
    if not stripped:
        return False
    # Markdown heading
    if re.match(r"^#{1,6}\s", stripped):
        return True
    # ALL CAPS line under 10 words
    words = stripped.split()
    if len(words) < 10 and stripped == stripped.upper() and any(c.isalpha() for c in stripped):
        return True
    # Short line (< 8 words) ending without punctuation
    if len(words) < 8 and stripped[-1] not in ".!?:;,":
        return True
    return False


def _is_caption(text: str) -> bool:
    """Detect figure/table captions."""
    return bool(re.match(r"(?i)^(figure|fig|table|chart|diagram)\s*\d*[:\.]", text.strip()))


class Chunker:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    #  MAIN ENTRY POINT (existing signature preserved)
    # ------------------------------------------------------------------

    def generate_chunks(self, subsection_id: int, document_id: int):
        """
        Refined sequence:
        1. Hierarchy exists (Subsection -> RawMaterial).
        2. Paragraph splitting (token-aware).
        3. Semantic refinement (merging).
        4. S, M, L derivation with overlap.
        """
        print(f"\n{'='*20} CHUNKING START (Subsection: {subsection_id}) {'='*20}")
        # Fetch subsection to get course_id if not passed (though we'll pass it from processor)
        sub = self.db.query(Subsection).get(subsection_id)
        course_id = sub.section.chapter.course_id if sub else None
        
        raw_material = self.db.query(RawMaterial).filter_by(subsection_id=subsection_id).first()
        if not raw_material:
            print(f"[ERROR] No raw material found for subsection {subsection_id}")
            return

        # Step 1: Token-aware paragraph splitting
        print(f"[1/3] Splitting raw text into paragraphs...")
        paragraphs = self._split_into_paragraphs(raw_material.content)
        # Token-aware sub-splitting for long paragraphs
        paragraphs = self._enforce_token_limit(paragraphs)
        print(f"      -> SUCCESS: Found {len(paragraphs)} logical paragraphs (S chunks)")

        # Step 2: Semantic Refinement (improved merge logic)
        print(f"[2/3] Applying Semantic Merger (AI-Logic)...")
        refined_paragraphs = self._semantic_merge(paragraphs)
        print(f"      -> SUCCESS: Refined into {len(refined_paragraphs)} meaningful explanations (M chunks)")

        # Multi-Granularity Derivation
        print(f"[3/3] Committing Multi-Granularity Index (S, M, L) to DB...")

        # Small (S) = Token-limited paragraphs with overlap
        small_chunks = self._add_overlap(paragraphs)
        self._create_chunks(subsection_id, small_chunks, ChunkType.SMALL, course_id=course_id, document_id=document_id)

        # Medium (M) = Refined (merged) paragraphs
        self._create_chunks(subsection_id, refined_paragraphs, ChunkType.MEDIUM, course_id=course_id, document_id=document_id)

        # Large (L) = Concept scope (Full text)
        self._create_l_chunk(subsection_id, raw_material.content, course_id=course_id, document_id=document_id)

        self.db.commit()
        print(f"{'='*20} CHUNKING COMPLETE {'='*24}\n")

    # ------------------------------------------------------------------
    #  STRUCTURED DOCX ENTRY POINT (new — Feature #5)
    # ------------------------------------------------------------------

    def chunk_structured(self, subsection_id: int, structured_paragraphs: List[Dict], course_id: Optional[int] = None, document_id: Optional[int] = None):
        """
        Alternate entry point for heading-structured input from DOCX extractor.
        Each dict: {"level": int, "text": str}
          level 1/2/3 = heading (section boundary)
          level 0     = body text
        Falls back to generate_chunks() if input is empty.
        """
        if not structured_paragraphs:
            return self.generate_chunks(subsection_id, document_id=document_id)
        
        if course_id is None:
            sub = self.db.query(Subsection).get(subsection_id)
            course_id = sub.section.chapter.course_id if sub else None

        print(f"\n{'='*20} STRUCTURED CHUNKING (Subsection: {subsection_id}) {'='*20}")

        # Collect body text between headings as MEDIUM chunk boundaries
        medium_chunks = []
        current_body = []
        current_heading = None

        for item in structured_paragraphs:
            level = item.get("level", 0)
            text = item.get("text", "").strip()
            if not text:
                continue

            if level in (1, 2, 3):
                # Flush accumulated body as a MEDIUM chunk
                if current_body:
                    body_text = "\n\n".join(current_body)
                    if current_heading:
                        body_text = current_heading + "\n\n" + body_text
                    medium_chunks.append(body_text)
                    current_body = []
                current_heading = text
            else:
                current_body.append(text)

        # Flush final block
        if current_body:
            body_text = "\n\n".join(current_body)
            if current_heading:
                body_text = current_heading + "\n\n" + body_text
            medium_chunks.append(body_text)

        # Build SMALL chunks from all body paragraphs (token-aware)
        all_body = [item["text"].strip() for item in structured_paragraphs
                     if item.get("level", 0) == 0 and item.get("text", "").strip()]
        small_paragraphs = self._enforce_token_limit(all_body)
        small_chunks = self._add_overlap(small_paragraphs)

        # Full text for LARGE chunk
        full_text = "\n\n".join(
            item["text"].strip() for item in structured_paragraphs if item.get("text", "").strip()
        )

        print(f"[STRUCTURED] {len(small_chunks)} SMALL, {len(medium_chunks)} MEDIUM, 1 LARGE")

        self._create_chunks(subsection_id, small_chunks, ChunkType.SMALL, course_id=course_id, document_id=document_id)
        self._create_chunks(subsection_id, medium_chunks, ChunkType.MEDIUM, course_id=course_id, document_id=document_id)
        self._create_l_chunk(subsection_id, full_text, course_id=course_id, document_id=document_id)

        self.db.commit()
        print(f"{'='*20} STRUCTURED CHUNKING COMPLETE {'='*14}\n")

    # ------------------------------------------------------------------
    #  TOKEN-AWARE SPLITTING (Feature #1)
    # ------------------------------------------------------------------

    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Splits text into paragraphs based on double newlines."""
        return [p.strip() for p in text.split('\n\n') if p.strip()]

    def _enforce_token_limit(self, paragraphs: List[str]) -> List[str]:
        """
        Ensures no paragraph exceeds MAX_CHUNK_TOKENS.
        Splits oversized paragraphs at sentence boundaries greedily.
        """
        result = []
        for para in paragraphs:
            tokens = count_tokens(para)
            if tokens <= MAX_CHUNK_TOKENS:
                result.append(para)
            else:
                # Split at sentence boundaries
                sentences = re.split(r'(?<=[.!?])\s+', para)
                current_chunk = ""
                current_tokens = 0

                for sentence in sentences:
                    s_tokens = count_tokens(sentence)
                    if current_tokens + s_tokens > MAX_CHUNK_TOKENS and current_chunk:
                        result.append(current_chunk.strip())
                        current_chunk = sentence
                        current_tokens = s_tokens
                    else:
                        current_chunk += (" " if current_chunk else "") + sentence
                        current_tokens += s_tokens

                if current_chunk.strip():
                    result.append(current_chunk.strip())

                # Safety check: warn if any resulting chunk still exceeds limit
                for chunk_text in result[-len(sentences):]:
                    if count_tokens(chunk_text) > MAX_CHUNK_TOKENS:
                        print(f"[WARNING] Chunk exceeds {MAX_CHUNK_TOKENS} tokens after sentence splitting ({count_tokens(chunk_text)} tokens)")

        return result

    # ------------------------------------------------------------------
    #  SEMANTIC MERGE (Feature #2 — improved)
    # ------------------------------------------------------------------

    def _semantic_merge(self, paragraphs: List[str]) -> List[str]:
        """
        Merges semantically related paragraphs with strict guards:
        - Never merge headings or captions
        - Only merge if the second paragraph starts with a continuation signal
        """
        if len(paragraphs) <= 1:
            return paragraphs

        merged = []
        i = 0
        while i < len(paragraphs):
            current = paragraphs[i]
            if i + 1 < len(paragraphs):
                next_p = paragraphs[i+1]
                if self._should_merge(current, next_p):
                    merged.append(current + " " + next_p)
                    i += 2
                    continue
            merged.append(current)
            i += 1
        return merged

    def _should_merge(self, p1: str, p2: str) -> bool:
        """
        Improved merge logic:
        - Never merge headings or captions
        - Only merge if p2 starts with a continuation signal
        """
        # Guard: never merge headings or captions
        if _is_heading(p1) or _is_heading(p2):
            return False
        if _is_caption(p1) or _is_caption(p2):
            return False

        # Only merge if p2 starts with a continuation signal
        p2_lower = p2.lower()
        if p2_lower.startswith(tuple(CONTINUATION_SIGNALS)):
            return True

        return False

    # ------------------------------------------------------------------
    #  OVERLAPPING CHUNKS (Feature #3)
    # ------------------------------------------------------------------

    def _add_overlap(self, paragraphs: List[str]) -> List[str]:
        """
        Adds overlap from the previous chunk to each SMALL chunk.
        Prepends the last paragraph of chunk[i-1] to chunk[i]
        separated by the OVERLAP_MARKER.
        Skips overlap if the result would exceed MAX_CHUNK_TOKENS.
        """
        if len(paragraphs) <= 1:
            return paragraphs

        result = [paragraphs[0]]  # First chunk has no overlap

        for i in range(1, len(paragraphs)):
            prev_content = paragraphs[i - 1]
            # Get the last paragraph/sentence of the previous chunk
            prev_parts = prev_content.split('\n\n')
            last_paragraph = prev_parts[-1].strip() if prev_parts else ""

            if last_paragraph:
                overlapped = last_paragraph + OVERLAP_MARKER + paragraphs[i]
                if count_tokens(overlapped) <= MAX_CHUNK_TOKENS:
                    result.append(overlapped)
                else:
                    # Skip overlap if it would exceed token limit
                    result.append(paragraphs[i])
            else:
                result.append(paragraphs[i])

        return result

    # ------------------------------------------------------------------
    #  PERSISTENCE (preserved)
    # ------------------------------------------------------------------

    def _create_chunks(self, subsection_id: int, text_list: List[str], chunk_type: ChunkType, course_id: Optional[int] = None, document_id: Optional[int] = None):
        for text in text_list:
            stripped = text.strip()
            # JUNK FILTER: Skip purely non-informative fragments
            if len(stripped) < 150:
                # If it's very short, check if it's just a header or logo text
                is_junk_header = _is_heading(stripped) or _is_caption(stripped)
                generic_keywords = ["HKUST", "Business School", "Center for", "Case Study", "Note", "Page", "Copyright"]
                is_generic = any(kw.lower() in stripped.lower() for kw in generic_keywords)
                
                if is_junk_header or is_generic:
                    print(f"[Chunking] Skipping non-informative chunk: '{stripped[:50]}...'")
                    continue

            chunk = Chunk(
                content=text,
                chunk_type=chunk_type,
                subsection_id=subsection_id,
                course_id=course_id,
                document_id=document_id
            )
            self.db.add(chunk)

    def _create_l_chunk(self, subsection_id: int, full_text: str, course_id: Optional[int] = None, document_id: Optional[int] = None):
        chunk = Chunk(
            content=full_text,
            chunk_type=ChunkType.LARGE,
            subsection_id=subsection_id,
            course_id=course_id,
            document_id=document_id
        )
        self.db.add(chunk)
