import json
from sqlalchemy.orm import Session
from ..database.models.question import Question, QuestionStatus
from ..database.models.transcript import Transcript, Quiz
from ..rag.evaluation import EvaluationService
from .rubric_evaluator import RubricEvaluationService
from datetime import datetime

class QuizManager:
    def __init__(self, db: Session, evaluation_service: EvaluationService):
        self.db = db
        self.eval_service = evaluation_service
        self.rubric_eval = RubricEvaluationService()

    def start_quiz(self, quiz_id: int, student_name: str, enrollment_id: str):
        """Initializes a quiz session for a student using a specific assessment link."""
        quiz = self.db.query(Quiz).get(quiz_id)
        if not quiz or not quiz.is_finalized:
            raise Exception("This assessment is not active.")
        
        return quiz.id

    def submit_answer(self, quiz_id: int, question_id: int, answer_text: str, student_name: str = None, enrollment_id: str = None):
        """
        Instant Submission:
        Logs raw student responses for academic audit. 
        Evaluation is NOT performed here to maximize throughput.
        """
        # Perform Evaluation
        from ..database.models.question import Question
        question = self.db.query(Question).get(question_id)
        
        eval_result = {"score": 0.0, "reasoning": "Evaluation failed"}
        if question:
            quiz = self.db.query(Quiz).get(quiz_id)
            instructions = quiz.instructions if quiz else None
            
            eval_result = self.eval_service.evaluate_answer(
                question_text=question.question_text,
                student_answer=answer_text,
                ideal_answer=question.ideal_answer,
                instructions=instructions
            )

        # --- AI Rubric Evaluation (additive, only when enabled) ---
        ai_eval_json = None
        quiz = self.db.query(Quiz).get(quiz_id)
        if quiz and quiz.ai_eval_enabled and quiz.ai_eval_rubric:
            try:
                rubric = json.loads(quiz.ai_eval_rubric)
                rubric_result = self.rubric_eval.evaluate(
                    question_text=question.question_text if question else "",
                    student_answer=answer_text,
                    rubric=rubric
                )
                if rubric_result:
                    ai_eval_json = json.dumps(rubric_result)
            except (json.JSONDecodeError, Exception) as e:
                print(f"[!] Rubric evaluation error: {e}")

        # Log Transcript (Academic Audit)
        transcript = Transcript(
            student_name=student_name,
            enrollment_id=enrollment_id,
            quiz_id=quiz_id,
            question_id=question_id,
            student_answer=answer_text,
            ai_evaluation=eval_result.get("reasoning", "LOGGED_FOR_AUDIT"),
            score=eval_result.get("score", 0.0),
            conceptual_gap=eval_result.get("conceptual_gap", False),
            ai_eval_results=ai_eval_json,
            time_taken_seconds=0
        )
        
        self.db.add(transcript)
        self.db.commit()
        
        return {
            "status": "Answer recorded successfully",
            "transcript_id": transcript.id
        }
