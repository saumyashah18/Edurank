from sqlalchemy.orm import Session
from ..rag.embedder import RAGService
from ..database.models.chunk import ChunkType
from ..quiz.llm_service import llm

class EvaluationService:
    def __init__(self, db: Session, rag_service: RAGService):
        self.db = db
        self.rag_service = rag_service
        self.llm = llm




    def evaluate_answer(self, question_text: str, student_answer: str, ideal_answer: str, instructions: str = None):
        """
        Evaluates a student answer strictly as an Audit / Dialogue record.
        IMPORTANT: This does NOT vectorize or embed the student's answer into the knowledge base.
        """
        # Retrieve relevant context ONLY (Student answer is used as a search query, not stored in FAISS)
        context_chunks = self.rag_service.retrieve(
            query=student_answer, 
            top_k=5, 
            chunk_types=[ChunkType.SMALL, ChunkType.MEDIUM]
        )
        
        context_text = "\n\n".join([c.content for c in context_chunks])
        chunk_ids = [c.id for c in context_chunks]

        prompt = f"""
        You are an academic evaluator. Evaluate the student's answer based on the provided reference material, the ideal answer, and the specific grading guidelines below.
        
        [GRADING STYLE GUIDELINES]
        {instructions if instructions else "Standard academic evaluation, fair and rigorous."}

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
        
        if "ERROR_RATE_LIMIT" in response_text:
            return {"score": 0.5, "reasoning": "AI Evaluation busy", "retrieved_chunk_ids": chunk_ids}

        # Parse AI response for score and reasoning
        import re
        # Support both 0.8 and 8/10 formats
        score_match = re.search(r"(?i)score[:\s*]+(\d+(?:\.\d+)?)", response_text)
        reasoning_match = re.search(r"(?i)reasoning[:\s*]+(.*?)(?=\d\.|Missing|\Z)", response_text, re.DOTALL)
        
        raw_score = float(score_match.group(1)) if score_match else 0.5
        # Normalize score to 0.0 - 1.0 if it seems to be out of 10 or 100
        if raw_score > 10:
            score = raw_score / 100
        elif raw_score > 1:
            score = raw_score / 10
        else:
            score = raw_score
            
        reasoning = reasoning_match.group(1).strip() if reasoning_match else response_text

        return {
            "score": score,
            "reasoning": reasoning,
            "retrieved_chunk_ids": chunk_ids
        }

