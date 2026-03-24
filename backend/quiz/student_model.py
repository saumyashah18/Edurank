from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database.models.concept import Concept
from ..database.models.student_concept_state import StudentConceptState

class StudentModelUpdater:
    def __init__(self, db: Session):
        self.db = db

    def update(
        self,
        student_id: str,
        quiz_id: int,
        course_id: int,
        score: float,
        misconception: str | None,
        recommended_action: str | None,
        concept_tags: list[str]
    ) -> list[StudentConceptState]:
        """
        Called after every answer submission.
        Finds or creates StudentConceptState for each concept_tag.
        Updates confidence, attempts, status, misconception, recommended_action.
        Returns the list of updated StudentConceptState rows.
        """
        updated_states = []

        for name in concept_tags:
            # Step 1: Look up Concept (case-insensitive)
            concept = self.db.query(Concept).filter(
                Concept.course_id == course_id,
                func.lower(Concept.name) == name.lower().strip()
            ).first()

            if not concept:
                continue

            # Step 2: Get or Create StudentConceptState
            state = self.db.query(StudentConceptState).filter_by(
                student_id=student_id,
                quiz_id=quiz_id,
                concept_id=concept.id
            ).first()

            if not state:
                state = StudentConceptState(
                    student_id=student_id,
                    quiz_id=quiz_id,
                    concept_id=concept.id,
                    status="not_tested",
                    confidence=0.0,
                    attempts=0
                )
                self.db.add(state)

            # Step 3: Update properties
            state.attempts += 1
            # Rolling average: (old_total_score + current_score) / new_attempts
            state.confidence = ((state.confidence * (state.attempts - 1)) + score) / state.attempts
            
            # Overwrite with latest diagnostic info
            state.misconception = misconception
            state.recommended_action = recommended_action
            
            # Update status
            state.status = self._compute_status(state.confidence, state.attempts)
            updated_states.append(state)

        # Step 5: Final commit
        try:
            self.db.commit()
            return updated_states
        except Exception as e:
            print(f"[StudentModelUpdater] Commit failed: {e}")
            self.db.rollback()
            return []

    def _compute_status(self, confidence: float, attempts: int) -> str:
        """Derives status from confidence score and attempt count."""
        # Use rounding to avoid floating point precision issues (e.g. 0.7999999999999999)
        score = round(confidence, 2)
        if score >= 0.8:
            return "demonstrated"
        elif score >= 0.5:
            return "partial"
        elif attempts >= 2:
            return "struggling"
        else:
            return "not_tested"
