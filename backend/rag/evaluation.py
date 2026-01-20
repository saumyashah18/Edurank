from sqlalchemy.orm import Session
from ..rag.embedder import RAGService
from ..database.models.chunk import ChunkType
from ..quiz.llm_service import llm

class EvaluationService:
    def __init__(self, db: Session, rag_service: RAGService):
        self.db = db
        self.rag_service = rag_service
        self.llm = llm




    def evaluate_answer(self, question_text: str, student_answer: str, ideal_answer: str):
        """
        Evaluates a student answer using Small (S) and Medium (M) chunks.
        """
        # Retrieve relevant S and M chunks for context
        context_chunks = self.rag_service.retrieve(
            query=student_answer, 
            top_k=5, 
            chunk_types=[ChunkType.SMALL, ChunkType.MEDIUM]
        )
        
        context_text = "\n\n".join([c.content for c in context_chunks])
        chunk_ids = [c.id for c in context_chunks]

        prompt = f"""
        You are an academic evaluator. Evaluate the student's answer based on the provided reference material and the ideal answer.
        
        Question: {question_text}
        Ideal Answer: {ideal_answer}
        Reference Material: {context_text}
        Student Answer: {student_answer}
        
        Provide:
        1. Score (0.0 to 1.0)
        2. Reasoning (Brief explanation of why this score was given)
        3. Any missing points from the syllabus.
        """
        
        response_text = self.llm.generate_content(prompt)

        # Simplified parsing of AI response
        # In production, use structured output (Schema/JSON)
        return {
            "score": 0.8, # Mocked
            "reasoning": response_text,
            "retrieved_chunk_ids": chunk_ids
        }

