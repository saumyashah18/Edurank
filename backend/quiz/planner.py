from sqlalchemy.orm import Session
from ..database.models.hierarchy import Chapter, Section, Subsection
from ..database.models.transcript import Transcript

class TopicPlanner:
    def __init__(self, db: Session):
        self.db = db

    def select_next_topic(self, course_id: int, enrollment_id: str = None, quiz_id: int = None, filter_keywords: list = None, used_chunk_ids: list = None):
        """
        Step 1: Live Topic Selection (Randomized per Student & Diverse)
        Uses enrollment_id as a seed so each student gets a unique but reproducible question order.
        """
        import random
        import hashlib
        from ..database.models.transcript import Transcript
        from ..database.models.question import Question
        from ..database.models.chunk import Chunk, ChunkType

        # 1. Identify used Chunk IDs and recently used authors
        if used_chunk_ids is None:
            used_chunk_ids = []
            
        recent_authors = []
        if enrollment_id and quiz_id:
            used_chunk_q = self.db.query(Question.chunk_id, Question.question_text).join(Transcript, Transcript.question_id == Question.id).filter(Transcript.enrollment_id == enrollment_id, Transcript.quiz_id == quiz_id).all()
            used_chunk_ids.extend([r[0] for r in used_chunk_q])
            
            # Track recent authors to avoid repetition
            for _, q_text in used_chunk_q[-3:]:
                q_text_lower = q_text.lower()
                for name in ["anjaria", "shapiro", "chatterjee", "held", "scott", "gupta", "ferguson", "palshikar", "jeffrey", "mehta", "khosla", "vaishnav"]:
                    if name in q_text_lower:
                        recent_authors.append(name)

        # 2. Fetch all chapters/sections for the course
        chapters = self.db.query(Chapter).filter_by(course_id=course_id).order_by(Chapter.order).all()
        
        candidates = []
        for chapter in chapters:
            for section in chapter.sections:
                for subsection in section.subsections:
                    # Filter by keywords if provided
                    matches_filter = True
                    if filter_keywords:
                        full_context = f"{chapter.title} {section.title} {subsection.title}".lower()
                        sample_chunk = self.db.query(Chunk).filter_by(subsection_id=subsection.id).first()
                        if sample_chunk:
                            full_context += " " + sample_chunk.content[:1000].lower()
                        matches_filter = any(k.lower() in full_context for k in filter_keywords)
                    
                    if matches_filter:
                        available_chunks = self.db.query(Chunk).filter(
                            Chunk.subsection_id == subsection.id,
                            Chunk.chunk_type == ChunkType.MEDIUM,
                            ~Chunk.id.in_(used_chunk_ids)
                        ).all()
                        
                        for chunk in available_chunks:
                            content_low = chunk.content[:500].lower()
                            author = "unknown"
                            for name in ["anjaria", "shapiro", "chatterjee", "held", "scott", "gupta", "ferguson", "palshikar", "jeffrey", "mehta", "khosla", "vaishnav"]:
                                if name in content_low:
                                    author = name
                                    break
                            
                            candidates.append({
                                "chunk": chunk,
                                "author": author
                            })

        # 3. Randomized Selection (per-student seed for variety)
        if candidates:
            # Create a deterministic seed from enrollment_id so each student
            # gets a DIFFERENT order, but their order is reproducible
            seed_str = enrollment_id or "professor_simulation"
            seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
            rng = random.Random(seed + len(used_chunk_ids))  # Shift seed each turn
            
            # Prefer chunks from authors NOT recently used (diversity)
            diverse_candidates = [c for c in candidates if c["author"] not in recent_authors and c["author"] != "unknown"]
            
            if diverse_candidates:
                rng.shuffle(diverse_candidates)
                chosen = diverse_candidates[0]
                return chosen["chunk"], chosen["author"]
            
            # Fallback: shuffle all candidates
            rng.shuffle(candidates)
            chosen = candidates[0]
            return chosen["chunk"], chosen["author"]
        
        return None, None

    def get_chunk_author(self, chunk):
        """Helper to identify the author of a chunk based on content heuristics."""
        if not chunk:
            return "unknown"
        content_low = chunk.content[:500].lower()
        for name in ["anjaria", "shapiro", "chatterjee", "held", "scott", "gupta", "ferguson", "palshikar", "jeffrey", "mehta", "khosla", "vaishnav"]:
            if name in content_low:
                return name
        return "the author"

    def _needs_more_exploration(self, subsection_id: int) -> bool:
        """Determines if a subsection needs more coverage based on total generated questions."""
        from ..database.models.question import Question
        q_count = self.db.query(Question).filter_by(subsection_id=subsection_id).count()
        return q_count < 20
