import json
from typing import Optional
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

    def submit_answer(self, quiz_id: int, question_id: int, answer_text: str, student_name: Optional[str] = None, enrollment_id: Optional[str] = None):
        """
        Instant Submission:
        Logs raw student responses for academic audit. 
        Evaluation is performed via QuizGraph subflow.
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

        # AI Rubric Evaluation
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
            except Exception as e:
                print(f"[!] Rubric evaluation error: {e}")

        # Log Transcript
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

        # Phase 7: LangGraph Orchestration for Evaluation/Hint/Update
        hint = None
        try:
            from .quiz_graph import QuizGraph
            from .quiz_state import QuizState

            eval_state: QuizState = {
                "student_id": enrollment_id or student_name or "anonymous",
                "quiz_id": quiz_id,
                "course_id": quiz.course_id if quiz else 0,
                "current_concept_id": None,
                "current_concept_name": None,
                "current_bloom_phase": 1,
                "current_question_id": question_id,
                "current_question_text": question.question_text if question else "",
                "current_chunk_id": question.chunk_id if question else None,
                "current_answer": answer_text,
                "last_score": eval_result.get("score", 0.0),
                "last_misconception": eval_result.get("misconception"),
                "last_recommended_action": eval_result.get("recommended_action"),
                "turn_number": 1,
                "total_questions": 10,
                "session_phase": "middle",
                "used_chunk_ids": [],
                "instructions": quiz.instructions if quiz else None,
                "output_question_text": None,
                "output_ideal_answer": None,
                "output_hint": None,
                "output_bloom_phase": 1,
                "output_concept_name": None,
                "output_session_phase": "middle",
                "output_error": None
            }

            graph = QuizGraph(self.db)
            eval_result_state = graph.run_evaluate(eval_state)
            hint = eval_result_state.get("output_hint")

        except Exception as graph_e:
            print(f"[QuizGraph] submit evaluate error: {graph_e}")

        return {
            "status": "Answer recorded successfully",
            "transcript_id": transcript.id,
            "hint": hint,
            "misconception": eval_result.get("misconception"),
            "recommended_action": eval_result.get("recommended_action")
        }

    def get_next_question(
        self,
        quiz_id: int,
        enrollment_id: str,
        student_name: Optional[str] = None,
        turn_number: int = 1,
        total_questions: int = 10,
        history_turns: Optional[list] = None,
        last_score: Optional[float] = None,
        last_misconception: Optional[str] = None,
        last_question_text: Optional[str] = None,
        last_chunk_id: Optional[int] = None
    ) -> dict:
        """
        Unified next-question endpoint logic.
        Handles session arc, concept selection, Bloom's phase, follow-ups, hints.
        """
        from .quiz_graph import QuizGraph
        from .quiz_state import QuizState
        from ..database.models.transcript import Quiz

        quiz = self.db.query(Quiz).get(quiz_id)
        if not quiz:
            return {"error": "Quiz not found."}

        course_id = quiz.course_id

        state: QuizState = {
            "student_id": enrollment_id,
            "quiz_id": quiz_id,
            "course_id": course_id,
            "current_concept_id": None,
            "current_concept_name": None,
            "current_bloom_phase": 1,
            "current_question_id": None,
            "current_question_text": None,
            "current_chunk_id": last_chunk_id,
            "current_answer": None,
            "last_score": last_score,
            "last_misconception": last_misconception,
            "last_recommended_action": None,
            "turn_number": turn_number,
            "total_questions": total_questions,
            "session_phase": "opening",
            "used_chunk_ids": [],
            "instructions": quiz.instructions if quiz else None,
            "output_question_text": None,
            "output_ideal_answer": None,
            "output_hint": None,
            "output_bloom_phase": 1,
            "output_concept_name": None,
            "output_session_phase": "opening",
            "output_error": None
        }

        graph = QuizGraph(self.db)
        result = graph.run_next_question(state)

        if result.get("output_error"):
            return {"error": result["output_error"]}

        return {
            "question_id": result["current_question_id"],
            "question_text": result["output_question_text"],
            "ideal_answer": result["output_ideal_answer"],
            "hint": result["output_hint"],
            "bloom_phase": result["output_bloom_phase"],
            "concept_name": result["output_concept_name"],
            "session_phase": result["output_session_phase"]
        }
