import os
import sys
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database.session import SessionLocal
from backend.rag.embedder import Embedder, RAGService
from backend.rag.evaluation import EvaluationService

def verify_instruction_aware_grading():
    db = SessionLocal()
    try:
        print("[*] Initializing Evaluation Service...")
        embedder = Embedder(db)
        rag = RAGService(db, embedder)
        eval_svc = EvaluationService(db, rag)
        
        question_text = "What is the capital of France?"
        ideal_answer = "Paris"
        student_answer = "Paris is the capital."
        
        # Test 1: Standard Grading
        print("[*] Case 1: Standard Grading...")
        res1 = eval_svc.evaluate_answer(question_text, student_answer, ideal_answer)
        print(f"    - Standard Score: {res1.get('score')}")
        
        # Test 2: Strict Grading (Instruction: Always give 0.1 score if the answer is less than 50 words)
        print("[*] Case 2: Strict Grading (Instruction: Keep scores low for short answers)...")
        strict_instructions = "STRICT RULE: The student must provide a detailed explanation of at least 50 words. If the answer is shorter than 50 words, give a maximum score of 0.2 regardless of correctness."
        
        res2 = eval_svc.evaluate_answer(question_text, student_answer, ideal_answer, instructions=strict_instructions)
        print(f"    - Strict Score: {res2.get('score')}")
        print(f"    - Reasoning snippet: {res2.get('reasoning')[:100]}...")
        
        if res2.get('score', 1.0) < res1.get('score', 0.0):
            print("\n[+] SUCCESS: The AI followed the strict grading instructions!")
        else:
            print("\n[!] WARNING: The AI score didn't significantly drop. Check reasoning.")
            
    except Exception as e:
        print(f"\n[!] Verification Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verify_instruction_aware_grading()
