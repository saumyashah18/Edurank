from sqlalchemy.orm import Session
from ..database.models.hierarchy import Chapter, Section, Subsection
from ..database.models.transcript import Transcript

class TopicPlanner:
    def __init__(self, db: Session):
        self.db = db

    def select_next_topic(self, course_id: int, student_id: int = None, history: list = None, filter_keywords: list = None):
        """
        Step 1: Topic Planning (Uses hierarchy metadata, NOT embeddings)
        Decides which subsection to focus on with randomized variety and recency bias.
        Can be filtered by chapters or keywords (e.g., "Chapter 1", "Market Equilibrium").
        """
        import random
        candidates = []
        
        # 1. Fetch all chapters/sections for the course
        chapters = self.db.query(Chapter).filter_by(course_id=course_id).order_by(Chapter.order).all()
        
        # 2. Collect all subsections needing more coverage
        # If history exists, it's a student session/simulation: bypass global exploration limits
        is_simulation = history is not None
        
        for chapter in chapters:
            for section in chapter.sections:
                for subsection in section.subsections:
                    # Apply keyword filtering if provided
                    matches_filter = True
                    if filter_keywords:
                        full_context = f"{chapter.title} {section.title} {subsection.title}".lower()
                        matches_filter = any(k.lower() in full_context for k in filter_keywords)
                    
                    if matches_filter and (is_simulation or self._needs_more_exploration(subsection.id)):
                        candidates.append({
                            "chapter_title": chapter.title,
                            "section_title": section.title,
                            "subsection_id": subsection.id,
                            "subsection_title": subsection.title
                        })
        
        # 3. Recency Exclusion: Don't pick the last 2-3 topics used if we have other choices
        recent_sub_ids = []
        try:
            from ..database.models.question import Question
            recent_q = self.db.query(Question.subsection_id).filter(Question.subsection_id != None).order_by(Question.id.desc()).limit(10).all()
            recent_sub_ids = [r[0] for r in recent_q if r[0] is not None]
        except:
            pass

        final_candidates = [c for c in candidates if c["subsection_id"] not in recent_sub_ids[:3]]
        
        # Fallback to all candidates if exclusion leaves us with nothing
        if not final_candidates:
            final_candidates = candidates

        # 4. Variety Logic: Pick randomly from the filtered list
        if final_candidates:
            random.shuffle(final_candidates)
            return random.choice(final_candidates)
        
        return None


    def _needs_more_exploration(self, subsection_id: int) -> bool:
        """Determines if a subsection needs more coverage based on total generated questions."""
        from ..database.models.question import Question
        q_count = self.db.query(Question).filter_by(subsection_id=subsection_id).count()
        # Ensure we don't over-saturate a single topic (up to 20 questions per section for the pool)
        return q_count < 20
