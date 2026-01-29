from sqlalchemy.orm import Session
from ..database.models.hierarchy import Chapter, Section, Subsection
from ..database.models.transcript import Transcript

class TopicPlanner:
    def __init__(self, db: Session):
        self.db = db

    def select_next_topic(self, course_id: int, enrollment_id: str = None, quiz_id: int = None, filter_keywords: list = None, used_chunk_ids: list = None):
        """
        Step 1: Live Topic Selection (Deterministic & Diverse)
        Excludes used chunks and balances authors (Anjaria, Shapiro, Chatterjee).
        """
        import random
        from ..database.models.transcript import Transcript
        from ..database.models.question import Question
        from ..database.models.chunk import Chunk, ChunkType

        # 1. Identify used Chunk IDs and recently used authors
        if used_chunk_ids is None:
            used_chunk_ids = []
            
        recent_authors = []
        if enrollment_id and quiz_id:
            # Fetch used chunks
            used_chunk_q = self.db.query(Question.chunk_id, Question.question_text).join(Transcript, Transcript.question_id == Question.id).filter(Transcript.enrollment_id == enrollment_id, Transcript.quiz_id == quiz_id).all()
            used_chunk_ids.extend([r[0] for r in used_chunk_q])
            
            # Simple heuristic for recent authors in last 3 questions
            for _, q_text in used_chunk_q[-3:]:
                q_text_lower = q_text.lower()
                if "anjaria" in q_text_lower: recent_authors.append("anjaria")
                if "shapiro" in q_text_lower: recent_authors.append("shapiro")
                if "chatterjee" in q_text_lower: recent_authors.append("chatterjee")

        # 2. Fetch all chapters/sections for the course
        chapters = self.db.query(Chapter).filter_by(course_id=course_id).order_by(Chapter.order).all()
        
        candidates = []
        for chapter in chapters:
            for section in chapter.sections:
                for subsection in section.subsections:
                    matches_filter = True
                    if filter_keywords:
                        full_context = f"{chapter.title} {section.title} {subsection.title}".lower()
                        matches_filter = any(k.lower() in full_context for k in filter_keywords)
                    
                    if matches_filter:
                        available_chunks = self.db.query(Chunk).filter(
                            Chunk.subsection_id == subsection.id,
                            Chunk.chunk_type == ChunkType.MEDIUM,
                            ~Chunk.id.in_(used_chunk_ids)
                        ).all()
                        
                        for chunk in available_chunks:
                            # 3. Author Heuristic (Check first 500 chars)
                            content_low = chunk.content[:500].lower()
                            author = "unknown"
                            if "anjaria" in content_low: author = "anjaria"
                            elif "shapiro" in content_low: author = "shapiro"
                            elif "chatterjee" in content_low: author = "chatterjee"
                            
                            candidates.append({
                                "chunk": chunk,
                                "author": author
                            })

        # 4. Deterministic Selection (Follow Syllabus Order)
        if candidates:
            # We follow the syllabus order (Chapter -> Section -> Subsection)
            # instead of random choice, so the teacher's preview order matches the student's.
            diverse_candidates = [c for c in candidates if c["author"] != "unknown" and c["author"] not in recent_authors]
            
            if diverse_candidates:
                chosen = diverse_candidates[0] # Pick the FIRST (chronological) instead of random
                return chosen["chunk"], chosen["author"]
            
            # Fallback to the first available candidate
            chosen = candidates[0]
            return chosen["chunk"], chosen["author"]
        
        return None, None

    def get_chunk_author(self, chunk):
        """Helper to identify the author of a chunk based on content heuristics."""
        if not chunk:
            return "unknown"
        # Detect author for current chunk manually if staying on same topic
        content_low = chunk.content[:500].lower()
        if "anjaria" in content_low: return "anjaria"
        if "shapiro" in content_low: return "shapiro"
        if "chatterjee" in content_low: return "chatterjee"
        return "the author"


    def _needs_more_exploration(self, subsection_id: int) -> bool:
        """Determines if a subsection needs more coverage based on total generated questions."""
        from ..database.models.question import Question
        q_count = self.db.query(Question).filter_by(subsection_id=subsection_id).count()
        # Ensure we don't over-saturate a single topic (up to 20 questions per section for the pool)
        return q_count < 20
