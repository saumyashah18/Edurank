import os
import json
from sqlalchemy.orm import Session
from backend.database.session import SessionLocal, init_db
from backend.quiz.quiz_manager import QuizManager
from backend.rag.embedder import Embedder, RAGService
from backend.rag.evaluation import EvaluationService
from backend.database.models.transcript import Transcript, Quiz
from backend.database.models.question import Question

def test_remedial_hardening():
    init_db()
    db = SessionLocal()
    try:
        # 1. Setup metadata
        quiz = db.query(Quiz).filter_by(id=13).first() or db.query(Quiz).first()
        if not quiz:
            print("No quiz found to test.")
            return
        quiz_id = quiz.id
        enrollment_id = "TEST_HARDEN_USER"
        student_name = "Harden Student"
        
        embedder = Embedder(db)
        rag = RAGService(db, embedder)
        eval_svc = EvaluationService(db, rag)
        manager = QuizManager(db, eval_svc)
        
        # --- Submit a WEAK answer to trigger Remedial mandate ---
        last_q = db.query(Question).first()
        print(f"\n--- Submitting WEAK answer to Q: {last_q.id} ---")
        weak_answer = "I have no idea what Class A or B shares are."
        
        manager.submit_answer(
            quiz_id=quiz_id,
            question_id=last_q.id,
            answer_text=weak_answer,
            student_name=student_name,
            enrollment_id=enrollment_id
        )
        
        print("\nRequesting Follow-up Question...")
        next_q_res = manager.get_next_question(
            quiz_id=quiz_id,
            enrollment_id=enrollment_id,
            student_name=student_name,
            turn_number=2
        )
        
        q_text = next_q_res.get('question_text', '')
        print(f"\nAI RESPONSE: {q_text}")
        
        # Check for conversational bridge
        bridges = ["You mentioned", "Regarding", "I see", "Based on your answer", "It seems", "Since you", "acknowledg"]
        has_bridge = any(bridge.lower() in q_text.lower() for bridge in bridges)
        
        if has_bridge:
            print("\nSUCCESS: AI acknowledged the previous answer as mandated.")
        else:
            print("\nFAILURE: AI jumped to a direct question without acknowledgement.")

    finally:
        db.close()

if __name__ == "__main__":
    test_remedial_hardening()
