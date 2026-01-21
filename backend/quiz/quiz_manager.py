from sqlalchemy.orm import Session
from ..database.models.question import Question, QuestionStatus
from ..database.models.transcript import Transcript, Quiz
from ..rag.evaluation import EvaluationService
from datetime import datetime

class QuizManager:
    def __init__(self, db: Session, evaluation_service: EvaluationService):
        self.db = db
        self.eval_service = evaluation_service

    def start_quiz(self, quiz_id: int, student_name: str, enrollment_id: str):
        """Initializes a quiz session for a student using a specific assessment link."""
        quiz = self.db.query(Quiz).get(quiz_id)
        if not quiz or not quiz.is_finalized:
            raise Exception("This assessment is not active.")
        
        # We don't create a NEW quiz record here anymore, we use the professor's finalized one.
        # But we could track completions in a separate 'ExamSession' if needed.
        # For now, we return the quiz_id as the session identifier.
        return quiz.id

    def submit_answer(self, quiz_id: int, question_id: int, answer_text: str, student_name: str = None, enrollment_id: str = None):
        """
        Instant Submission:
        Logs raw student responses for academic audit. 
        Evaluation is NOT performed here to maximize throughput.
        """
        # Log Transcript (Academic Audit)
        transcript = Transcript(
            student_name=student_name,
            enrollment_id=enrollment_id,
            quiz_id=quiz_id,
            question_id=question_id,
            student_answer=answer_text,
            ai_evaluation="LOGGED_FOR_AUDIT",
            score=0.0, # Placeholder, logic moved to implicit adaptive eval
            time_taken_seconds=0
        )
        
        self.db.add(transcript)
        self.db.commit()
        
        return {
            "status": "Answer recorded successfully",
            "transcript_id": transcript.id
        }
