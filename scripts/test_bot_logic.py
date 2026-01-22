import sys
import os

# Mocking the environment for a quick check
sys.path.append(os.getcwd())
from backend.database.session import SessionLocal
from backend.quiz.professor_bot import ProfessorBot
from backend.quiz.planner import TopicPlanner
from backend.rag.embedder import RAGService, Embedder

def test_bot():
    db = SessionLocal()
    planner = TopicPlanner(db)
    rag = RAGService(db, Embedder(db))
    bot = ProfessorBot(db, rag, planner)
    
    print("\n--- TEST 1: Phase 0 (No History) ---")
    q1 = bot.generate_single_question(course_id=1, history=[])
    print(f"Bot Output: {q1.question_text}")
    print(f"Context: {q1.ideal_answer}")

    print("\n--- TEST 2: Multi-turn (Comparison Potential) ---")
    history = [
        {"q": "Hi! Which author do you like?", "a": "I like Partha Chatterjee."}
    ]
    # We will simulate multiple calls to see if comparison chunk triggers
    for i in range(3):
        q = bot.generate_single_question(course_id=1, history=history)
        if q:
            print(f"Turn {i+1} Output: {q.question_text[:100]}...")
        else:
            print(f"Turn {i+1} failed (no chunks found?)")

    db.close()

if __name__ == "__main__":
    test_bot()
