import os
import sys
from sqlalchemy.orm import Session
from backend.database.session import SessionLocal
from backend.rag.evaluation import EvaluationService
from backend.rag.embedder import RAGService, Embedder

def test_evaluation():
    db = SessionLocal()
    try:
        embedder = Embedder(db)
        rag = RAGService(db, embedder)
        eval_service = EvaluationService(db, rag)
        
        test_questions = [
            ("What is the capital of France?", "I don't know", "The capital of France is Paris."),
            ("How does photosynthesis work?", "It uses water and air to make things.", "Photosynthesis is the process by which green plants and some other organisms use sunlight to synthesize foods with the help of chlorophyll, water, and carbon dioxide."),
            ("What is 1+1?", "3", "1+1 is 2.")
        ]
        
        for q, a, ideal in test_questions:
            print(f"\n--- Testing: {q} | Ans: {a} ---")
            res = eval_service.evaluate_answer(q, a, ideal)
            print(f"Score: {res['score']}")
            print(f"Reasoning: {res['reasoning'][:100]}...")
            print(f"Conceptual Gap: {res['conceptual_gap']}")
            print(f"Misconception: {res['misconception']}")
            print(f"Action: {res['recommended_action']}")
            
    finally:
        db.close()

if __name__ == "__main__":
    test_evaluation()
