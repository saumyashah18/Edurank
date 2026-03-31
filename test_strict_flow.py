import os
import json
from sqlalchemy.orm import Session
from backend.database.session import SessionLocal, init_db
from backend.quiz.quiz_manager import QuizManager
from backend.rag.embedder import Embedder, RAGService
from backend.rag.evaluation import EvaluationService
from backend.database.models.transcript import Transcript, Quiz
from backend.database.models.question import Question

def test_strict_flow():
    init_db()
    db = SessionLocal()
    try:
        # 1. Setup metadata
        quiz = db.query(Quiz).filter_by(id=13).first() or db.query(Quiz).first()
        if not quiz:
            print("No quiz found to test.")
            return
        quiz_id = quiz.id
        enrollment_id = "TEST_STRICT_USER"
        student_name = "Strict Student"
        
        embedder = Embedder(db)
        rag = RAGService(db, embedder)
        eval_svc = EvaluationService(db, rag)
        manager = QuizManager(db, eval_svc)
        
        # --- Case A: Correct Answer (Should NOT trigger follow-up or Phase 2) ---
        last_q = db.query(Question).first()
        print(f"\n--- Case A: Submitting a CORRECT answer to Q: {last_q.id} ---")
        correct_answer = last_q.ideal_answer
        
        manager.submit_answer(
            quiz_id=quiz_id,
            question_id=last_q.id,
            answer_text=correct_answer,
            student_name=student_name,
            enrollment_id=enrollment_id
        )
        
        print("\nRequesting Next Question (Should be Phase 1, Follow-up False)...")
        next_q_res = manager.get_next_question(
            quiz_id=quiz_id,
            enrollment_id=enrollment_id,
            student_name=student_name,
            turn_number=2
        )
        # We check the printed logs for ProfessorBot Phase/Follow-up
        print(f"Result: {next_q_res.get('question_text')[:100]}...")

        # --- Case B: Incorrect Answer (SHOULD trigger Remedial Phase 2) ---
        enrollment_id_2 = "TEST_STRICT_USER_FAIL"
        print(f"\n--- Case B: Submitting a WEAK answer to Q: {last_q.id} ---")
        weak_answer = "I don't know anything about this topic."
        
        manager.submit_answer(
            quiz_id=quiz_id,
            question_id=last_q.id,
            answer_text=weak_answer,
            student_name=student_name,
            enrollment_id=enrollment_id_2
        )
        
        print("\nRequesting Next Question (Should be Phase 2, Follow-up True)...")
        next_q_res_2 = manager.get_next_question(
            quiz_id=quiz_id,
            enrollment_id=enrollment_id_2,
            student_name=student_name,
            turn_number=2
        )
        print(f"Result: {next_q_res_2.get('question_text')[:100]}...")

    finally:
        db.close()

if __name__ == "__main__":
    test_strict_flow()
