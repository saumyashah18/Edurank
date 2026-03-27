from typing import Optional
from sqlalchemy.orm import Session
from ..rag.embedder import RAGService
from ..utils.llm_logger import LLMCallLogger
from ..database.models.chunk import ChunkType
from ..quiz.llm_service import llm

class EvaluationService:
    def __init__(self, db: Session, rag_service: RAGService):
        self.db = db
        self.rag_service = rag_service
        self.llm = llm




    def evaluate_answer(self, question_text: str, student_answer: str, ideal_answer: str, instructions: Optional[str] = None):
        """
        Evaluates a student answer strictly as an Audit / Dialogue record.
        IMPORTANT: This does NOT vectorize or embed the student's answer into the knowledge base.
        """
        # Retrieve relevant context ONLY (Student answer is used as a search query, not stored in the knowledge base)
        context_chunks = LLMCallLogger.timed_call(
            caller="RAGService.retrieve",
            prompt=student_answer, # Using student_answer as the query for logging
            llm_fn=lambda: self.rag_service.retrieve(
                query=student_answer,
                top_k=5,
                chunk_types=[ChunkType.SMALL, ChunkType.MEDIUM]
            ),
            extra={"question_text": question_text}
        )

        # Phase 8: Retrieval logging
        for c in context_chunks:
            print(f"[RAG_RETRIEVAL] chunk_id={c.id} type={c.chunk_type.value} subsection={c.subsection_id}")

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
        4. Conceptual Gap Detected (True/False - set to True ONLY if the student demonstrates a fundamental misunderstanding. If they made a minor error, set to False).
        """
        
        response_text = LLMCallLogger.timed_call(
            caller="EvaluationService",
            prompt=prompt,
            llm_fn=lambda: self.llm.generate_content(prompt),
            extra={"question_chars": len(question_text), "answer_chars": len(student_answer)}
        )
        
        if "ERROR_RATE_LIMIT" in response_text:
            return {"score": 0.5, "reasoning": "AI Evaluation busy", "conceptual_gap": False, "retrieved_chunk_ids": chunk_ids}

        # Parse AI response for score and reasoning
        import re
        # Support both 0.8 and 8/10 formats
        score_match = re.search(r"(?i)score[:\s*]+(\d+(?:\.\d+)?)", response_text)
        reasoning_match = re.search(r"(?i)reasoning[:\s*]+(.*?)(?=\d\.|Missing|Conceptual|\Z)", response_text, re.DOTALL)
        gap_match = re.search(r"(?i)Conceptual Gap Detected[:\s*]+(Yes|No|True|False)", response_text)
        
        raw_score = float(score_match.group(1)) if score_match else 0.5
        # Normalize score to 0.0 - 1.0 if it seems to be out of 10 or 100
        if raw_score > 10:
            score = raw_score / 100
        elif raw_score > 1:
            score = raw_score / 10
        else:
            score = raw_score
            
        reasoning = reasoning_match.group(1).strip() if reasoning_match else response_text
        conceptual_gap = True if gap_match and gap_match.group(1).lower() in ["yes", "true"] else False

        # Phase 5: Misconception Detection & Concept Tagging
        misconception_data = self._detect_misconception(question_text, student_answer, score, reasoning)

        return {
            "score": score,
            "reasoning": reasoning,
            "conceptual_gap": conceptual_gap,
            "retrieved_chunk_ids": chunk_ids,
            "misconception": misconception_data.get("misconception"),
            "recommended_action": misconception_data.get("recommended_action"),
            "concept_tags": misconception_data.get("concept_tags", [])
        }

    def _detect_misconception(self, question_text: str, student_answer: str, score: float, reasoning: str) -> dict:
        """
        Deep diagnostic analysis of a student's answer to identify conceptual gaps.
        Only runs for scores < 0.85 to optimize performance.
        """
        if score >= 0.85:
            return {
                "misconception": None,
                "recommended_action": "move_on",
                "concept_tags": []
            }

        system_prompt = (
            "You are an academic diagnostic tool. Analyse student answers to identify conceptual gaps. "
            "Respond ONLY with valid JSON. No preamble, no markdown, no code fences."
        )

        user_prompt = f"""A student answered an exam question. Diagnose their understanding.

   QUESTION: {question_text}
   STUDENT ANSWER: {student_answer}
   SCORE: {score:.2f} / 1.0
   EVALUATOR NOTES: {reasoning}

   Identify:
   1. The specific misconception or knowledge gap (one clear sentence, or null if none)
   2. The recommended next action:
      - "drop_to_prerequisite": student is missing foundational knowledge
      - "retry_rephrase": student partially understands, needs rephrasing
      - "deepen": student understands basics but needs deeper engagement
      - "move_on": student demonstrated sufficient understanding
   3. concept_tags: 2-5 short concept names this question tests (noun phrases, 2-4 words each)

   Respond with EXACTLY:
   {{
     "misconception": "<one sentence or null>",
     "recommended_action": "<drop_to_prerequisite|retry_rephrase|deepen|move_on>",
     "concept_tags": ["<concept>", "<concept>"]
   }}"""

        response = LLMCallLogger.timed_call(
            caller="MisconceptionDetector",
            prompt=user_prompt,
            llm_fn=lambda: self.llm.generate_content(user_prompt, system_prompt=system_prompt),
            extra={"score": float(round(score, 3))}
        )
        
        # Strip markdown fences
        import json
        clean_json = response.strip()
        if clean_json.startswith("```"):
            lines = clean_json.split("\n")
            if lines[0].startswith("```"): lines = lines[1:]
            if lines[-1].strip() == "```": lines = lines[:-1]
            clean_json = "\n".join(lines).strip()

        try:
            data = json.loads(clean_json)
            # Validation
            allowed_actions = {"drop_to_prerequisite", "retry_rephrase", "deepen", "move_on"}
            if data.get("recommended_action") not in allowed_actions:
                data["recommended_action"] = "retry_rephrase"
            return data
        except Exception as e:
            print(f"[MisconceptionDetector] parse error: {e}")
            return {
                "misconception": None,
                "recommended_action": "retry_rephrase",
                "concept_tags": []
            }


