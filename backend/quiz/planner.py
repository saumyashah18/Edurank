from sqlalchemy.orm import Session
from ..database.models.hierarchy import Chapter, Section, Subsection
from ..database.models.transcript import Transcript

class TopicPlanner:
    def __init__(self, db: Session):
        self.db = db

    def select_next_topic(self, course_id: int, student_id: int):
        """
        Step 1: Topic Planning (Uses hierarchy metadata, NOT embeddings)
        Decides which subsection to focus on with randomized variety.
        """
        import random
        candidates = []
        
        # 1. Fetch all chapters/sections for the course
        chapters = self.db.query(Chapter).filter_by(course_id=course_id).order_by(Chapter.order).all()
        
        # 2. Collect all subsections needing more coverage
        for chapter in chapters:
            for section in chapter.sections:
                for subsection in section.subsections:
                    if self._needs_more_exploration(subsection.id):
                        candidates.append({
                            "chapter_title": chapter.title,
                            "section_title": section.title,
                            "subsection_id": subsection.id,
                            "subsection_title": subsection.title
                        })
        
        # 3. Pick one randomly to ensure syllabus-wide variety
        if candidates:
            return random.choice(candidates)
        
        return None


    def _needs_more_exploration(self, subsection_id: int) -> bool:
        # Business logic for coverage control
        # e.g., "Have I already asked too many questions from this concept?"
        # For now, return True if we have less than 3 questions generated here.
        from ..database.models.question import Question
        q_count = self.db.query(Question).filter_by(subsection_id=subsection_id).count()
        return q_count < 5
