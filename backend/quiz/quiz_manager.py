from sqlalchemy.orm import Session
from ..database.models.question import Question, QuestionStatus
from ..database.models.transcript import Transcript, Quiz
from ..rag.evaluation import EvaluationService
from datetime import datetime

class QuizManager:
    def __init__(self, db: Session, evaluation_service: EvaluationService):
        self.db = db
        self.eval_service = evaluation_service

    def start_quiz(self, course_id: int, student_id: int):
        """Initializes a quiz session for a student."""
        # Check for approved questions in the course
        # This is a simplified fetch
        quiz = Quiz(course_id=course_id, title=f"Quiz - {datetime.now().date()}")
        self.db.add(quiz)
        self.db.commit()
        return quiz.id

    def submit_answer(self, student_id: int, quiz_id: int, question_id: int, answer_text: str):
        """
        Processes a student answer:
        1. Fetches question and ideal answer.
        2. Evaluates using RAG (S+M chunks).
        3. Logs full transcript.
        """
        question = self.db.query(Question).get(question_id)
        if not question or question.status != QuestionStatus.APPROVED:
            raise Exception("Invalid or unapproved question.")

        # Evaluation
        eval_result = self.eval_service.evaluate_answer(
            question.question_text, 
            answer_text, 
            question.ideal_answer
        )

        # Log Transcript (Academic Audit)
        transcript = Transcript(
            student_id=student_id,
            quiz_id=quiz_id,
            question_id=question_id,
            student_answer=answer_text,
            ai_evaluation=eval_result["reasoning"],
            score=eval_result["score"],
            retrieved_chunk_ids=",".join(map(str, eval_result["retrieved_chunk_ids"])),
            time_taken_seconds=30 # Mocked
        )
        
        self.db.add(transcript)
        self.db.commit()
        
        return {
            "status": "Answer submitted",
            "transcript_id": transcript.id
        }
