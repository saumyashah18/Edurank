import os
import sys
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database.session import SessionLocal
from backend.rag.embedder import Embedder, RAGService
from backend.rag.evaluation import EvaluationService
from backend.database.models.question import Question

def verify_fix():
    db = SessionLocal()
    try:
        print("[*] Initializing Services...")
        embedder = Embedder(db)
        rag = RAGService(db, embedder)
        eval_svc = EvaluationService(db, rag)
        
        # Get first question
        question = db.query(Question).first()
        if not question:
            print("[!] No questions found to test with.")
            return

        print(f"[*] Testing Evaluation for Question: {question.question_text[:50]}...")
        
        student_answer = "Digital technologies disrupt states by commodifying data and creating new forms of surveillance."
        
        res = eval_svc.evaluate_answer(
            question_text=question.question_text,
            student_answer=student_answer,
            ideal_answer=question.ideal_answer
        )
        
        print(f"\n[+] SUCCESS!")
        print(f"    - Score: {res.get('score')}")
        print(f"    - Reasoning: {res.get('reasoning')[:100]}...")
        print(f"    - Retrieved Chunks: {len(res.get('retrieved_chunk_ids', []))}")
        
    except Exception as e:
        print(f"\n[!] Verification Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verify_fix()
