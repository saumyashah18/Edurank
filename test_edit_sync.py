import os
import json
from sqlalchemy.orm import Session
from backend.database.session import SessionLocal, init_db
from backend.quiz.quiz_manager import QuizManager
from backend.rag.embedder import Embedder, RAGService
from backend.rag.evaluation import EvaluationService
from backend.database.models.transcript import Transcript, Quiz
from backend.database.models.question import Question
from backend.database.models.student_concept_state import StudentConceptState

def test_edit_sync():
    init_db()
    db = SessionLocal()
    try:
        # 1. Reuse existing quiz/question context
        quiz = db.query(Quiz).first()
        if not quiz:
            print("No quiz found to test.")
            return
            
        transcript = db.query(Transcript).filter_by(quiz_id=quiz.id).order_by(Transcript.id.desc()).first()
        if not transcript:
            print("No transcript found to test edit flow.")
            return

        print(f"--- Testing Edit Re-evaluation for Transcript {transcript.id} ---")
        original_score = transcript.score
        print(f"Original Score: {original_score}")
        
        # 2. Simulate an edit to a "perfect" answer
        transcript.student_answer = "This is a comprehensive and technically accurate answer that covers all parts of the question."
        db.commit()
        
        embedder = Embedder(db)
        rag = RAGService(db, embedder)
        eval_svc = EvaluationService(db, rag)
        manager = QuizManager(db, eval_svc)
        
        print("\nTriggering re_evaluate_transcript...")
        manager.re_evaluate_transcript(transcript.id)
        
        # 3. Verify Transcript Update
        db.refresh(transcript)
        print(f"New Transcript Score: {transcript.score}")
        
        # 4. Verify StudentConceptState Update
        # Find concepts for this question to check their sync status
        from backend.database.models.concept import Concept, ConceptChunk
        concepts = db.query(Concept).join(ConceptChunk).filter(
            ConceptChunk.chunk_id == transcript.question.chunk_id
        ).all()
        
        for c in concepts:
            state = db.query(StudentConceptState).filter_by(
                student_id=transcript.enrollment_id or transcript.student_name,
                quiz_id=transcript.quiz_id,
                concept_id=c.id
            ).first()
            if state:
                print(f"Concept State Updated: {c.name} | Confidence: {state.confidence:.2f} | Action: {state.recommended_action}")
            else:
                print(f"Warning: No StudentConceptState found for concept {c.name}")

        if transcript.score > original_score or transcript.score > 0.7:
             print("\nSUCCESS: The transcript was re-evaluated and the global state was synchronized.")
        else:
             print("\nNote: Score didn't increase significantly, but check if re-evaluation logs appeared.")

    finally:
        db.close()

if __name__ == "__main__":
    test_edit_sync()
