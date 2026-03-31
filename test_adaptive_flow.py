import os
import json
from sqlalchemy.orm import Session
from backend.database.session import SessionLocal, init_db
from backend.quiz.quiz_manager import QuizManager
from backend.rag.embedder import Embedder, RAGService
from backend.rag.evaluation import EvaluationService
from backend.database.models.transcript import Transcript, Quiz
from backend.database.models.question import Question

def test_adaptive_flow():
    init_db()
    db = SessionLocal()
    try:
        # 1. Setup metadata
        # Dynamically find a valid quiz
        quiz = db.query(Quiz).first()
        if not quiz:
            print("No quizzes found in DB. Run ingestion/quiz creation first.")
            return
        quiz_id = quiz.id
        print(f"Using Quiz ID: {quiz_id} ({quiz.title})")
        
        enrollment_id = "TEST_ADAPTIVE_USER_2"
        student_name = "Adaptive Student"
        
        embedder = Embedder(db)
        rag = RAGService(db, embedder)
        eval_svc = EvaluationService(db, rag)
        manager = QuizManager(db, eval_svc)
        
        # 2. Start from a known state or just pick any question
        # If no questions exist, we can't test. Let's assume some exist.
        last_q = db.query(Question).first()
        if not last_q:
            print("No questions found in DB to test with. Run ingestion first.")
            return

        print(f"--- Step 1: Submitting a weak answer to Q: {last_q.question_text[:50]}... ---")
        # Answer is intentionally poor to trigger conceptual gap
        weak_answer = "I think it has something to do with money, but I don't really know how it works."
        
        submit_res = manager.submit_answer(
            quiz_id=quiz_id,
            question_id=last_q.id,
            answer_text=weak_answer,
            student_name=student_name,
            enrollment_id=enrollment_id
        )
        print(f"Submission Score: {submit_res.get('recommended_action')}")
        
        # 3. Request next question and check if it's a follow-up
        print("\n--- Step 2: Requesting Next Question (should be a follow-up) ---")
        # We simulate the turn count
        turn_count = db.query(Transcript).filter_by(enrollment_id=enrollment_id, quiz_id=quiz_id).count()
        
        next_q_res = manager.get_next_question(
            quiz_id=quiz_id,
            enrollment_id=enrollment_id,
            student_name=student_name,
            turn_number=turn_count + 1
        )
        
        print(f"Next Question Text: {next_q_res.get('question_text')}")
        # Note: The logs will show "Follow-up: True" if it worked
        
        # Check if the question mentions "money" (connecting to previous answer)
        q_text = next_q_res.get('question_text', "").lower()
        if "money" in q_text or "mentioned" in q_text or "point" in q_text:
            print("\nSUCCESS: The next question appears to be connected to the previous answer!")
        else:
            print("\nWARNING: The connection to the previous answer might not be explicit in the text, check ProfessorBot logs.")

    finally:
        db.close()

if __name__ == "__main__":
    test_adaptive_flow()
