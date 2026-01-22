from typing import List, Dict
from sqlalchemy.orm import Session
from ..rag.embedder import RAGService
from ..database.models.chunk import ChunkType, Chunk
from ..database.models.question import Question, QuestionStatus
from ..database.models.transcript import Quiz
from .planner import TopicPlanner
from .llm_service import llm


class ProfessorBot:
    def __init__(self, db: Session, rag_service: RAGService, planner: TopicPlanner):
        self.db = db
        self.rag_service = rag_service
        self.planner = planner
        self.llm = llm
        self.instructions = None # To be fetched per course




    def generate_questions_for_course(self, course_id: int, total_marks: int = 100):
        """
        Pool Generation Phase:
        Generates a robust batch of questions to ensure students never hit JIT delays.
        """
        # Fetch instructions
        quiz_config = self.db.query(Quiz).filter_by(course_id=course_id).order_by(Quiz.id.desc()).first()
        self.instructions = quiz_config.instructions if quiz_config else None

        batch_limit = 15 # INCREASED: Ensure a deep pool for variety and throughput
        total_generated = 0
        processed_subsections = []

        print(f"\n[AI GENERATOR] Pool Generation: Targeting {batch_limit} diverse questions for Course {course_id}")

        for _ in range(batch_limit):
            question = self.generate_single_question(course_id)
            if question:
                total_generated += 1
                processed_subsections.append(question.subsection_id)
        
        return f"Pool Ready: Generated {total_generated} diverse questions for the assessment."

    def generate_single_question(self, course_id: int, history: List[Dict[str, str]] = None):
        """Generates ONE question grounded in the chunk, adapted to student history if provided."""
        # 1. Selection
        # If we have history, we might want to stay on a topic or move based on performance
        topic = self.planner.select_next_topic(course_id, student_id=None)
        if not topic:
            return None

        m_chunk = self.db.query(Chunk).filter_by(
            subsection_id=topic["subsection_id"],
            chunk_type=ChunkType.MEDIUM
        ).first()

        if not m_chunk:
            return None

        # 2. Generation with Adaptive Logic
        return self._create_question_from_m_chunk(m_chunk, topic["subsection_id"], history)




    def _create_question_from_m_chunk(self, chunk: Chunk, subsection_id: int, history: List[Dict[str, str]] = None):
        """Generates a question following Coursera-style adaptive dialogue logic."""
        
        default_system = "You are an examiner. Generate short-answer questions based on the provided material."
        
        # Build history context
        history_context = ""
        if history:
            history_context = "\n### DIALOGUE SO FAR:\n"
            for turn in history[-3:]: 
                history_context += f"AI: {turn.get('q')}\nSTUDENT: {turn.get('a')}\n---\n"

        user_prompt = f"""
        [Syllabus Context]
        {chunk.content}

        [Current Conversation]
        {history_context}

        [Task]
        You are an AI Examiner. Based on the syllabus context and the student's previous responses, ask the NEXT logical question. 
        - If the student is knowledgeable, progress to more complex aspects of this topic.
        - If the student is vague, ask a follow-up to clarify.
        - DO NOT repeat yourself.
        - DO NOT provide evaluation, feedback, or answers.
        - Return ONLY the question text.
        """

        system_prompt = self.instructions if self.instructions else "You are an examiner. Generate the next question."

        print(f"DEBUG: JIT Question Generation for chunk {chunk.id}...")
        q_text = self.llm.generate_content(user_prompt, system_prompt=system_prompt).strip()
        
        # Prepend transition if history exists
        if history:
            import random
            transitions = [
                "I see. Moving forward,",
                "That makes sense. Let's explore further:",
                "Alright, let's look at the next aspect:",
                "Got it. Here is the next question for you:",
                "Understood. Let's dive deeper:",
                "Good. Now, consider this:"
            ]
            q_text = f"{random.choice(transitions)} {q_text}"

        question = Question(
            question_text=q_text,
            ideal_answer="SOURCE_MATERIAL_REFERENCE", # No longer generating JIT to save time
            status=QuestionStatus.PENDING,
            chunk_id=chunk.id,
            subsection_id=subsection_id
        )
        self.db.add(question)
        self.db.commit()
        return question


    def _parse_ai_response(self, text: str):
        """Robust parser for AI-generated assessment content, handling markdown and flexible tagging."""
        print(f"DEBUG: Raw AI Response:\n{text}\n{'-'*30}")
        import re
        
        # Look for "Question:" and "Ideal Answer:" even if inside markdown like **Question:**
        q_match = re.search(r"(?:\*\*|#)?\s*(?:Question|QUESTION)[:\s*]+(.*?)(?=(?:\*\*|#)?\s*(?:Ideal Answer|IDEAL ANSWER)|$)", text, re.DOTALL | re.IGNORECASE)
        a_match = re.search(r"(?:\*\*|#)?\s*(?:Ideal Answer|IDEAL ANSWER)[:\s*]+(.*)", text, re.DOTALL | re.IGNORECASE)
        
        q_text = q_match.group(1).strip() if q_match else None
        a_text = a_match.group(1).strip() if a_match else None
        
        if q_text and a_text:
            # Clean up residual markdown if any (like trailing ***)
            q_text = re.sub(r"\*\*+$", "", q_text).strip()
            a_text = re.sub(r"\*\*+$", "", a_text).strip()
            return q_text, a_text
            
        return "Failed to parse question.", "Consult source material."

