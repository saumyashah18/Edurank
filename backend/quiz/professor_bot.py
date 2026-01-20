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
        Batch Generation Flow:
        Iterates through multiple subsections to create a large variety of questions.
        """
        # Fetch instructions for this course (from the latest quiz config)
        quiz_config = self.db.query(Quiz).filter_by(course_id=course_id).order_by(Quiz.id.desc()).first()
        self.instructions = quiz_config.instructions if quiz_config else None
        
        if self.instructions:
            print(f"[AI] Using System Instructions: {self.instructions[:50]}...")
        else:
            print("[AI] No instructions found. Using default short-answer mode.")

        batch_limit = 10 # Process up to 10 subsections per click
        total_generated = 0
        processed_subsections = []

        print(f"\n[AI GENERATOR] Batch Start: Targeting {batch_limit} subsections for Course {course_id}")

        for _ in range(batch_limit):
            # Step 1: Planning (Get a subsection that needs more questions)
            topic = self.planner.select_next_topic(course_id, student_id=None)
            if not topic or topic["subsection_id"] in processed_subsections:
                break

            processed_subsections.append(topic["subsection_id"])
            print(f"  > Processing Topic: {topic['subsection_title']}...")

            # Step 2: Selection (Medium chunks for planned subsection)
            m_chunks = self.db.query(Chunk).filter_by(
                subsection_id=topic["subsection_id"],
                chunk_type=ChunkType.MEDIUM
            ).limit(3).all() # Generate ~3 questions per subsection for variety

            if not m_chunks:
                print(f"    [!] No Medium chunks found for {topic['subsection_title']}. Skipping.")
                continue

            # Step 3: Generation
            for chunk in m_chunks:
                try:
                    self._create_question_from_m_chunk(chunk, topic["subsection_id"])
                    total_generated += 1
                except Exception as e:
                    print(f"    [!] Generation failed for chunk {chunk.id}: {e}")
        
        return f"Batch Complete: Generated {total_generated} questions across {len(processed_subsections)} topics."




    def _create_question_from_m_chunk(self, chunk: Chunk, subsection_id: int):
        """Generates a question grounded in the chunk, following system instructions if provided."""
        
        # Default prompt if no instructions are provided
        default_system = "You are an examiner. Generate short-answer questions based on the provided material."
        
        user_prompt = f"""
        [CRITICAL GATING]
        FOLLOW THESE SYSTEM INSTRUCTIONS EXACTLY:
        {self.instructions if self.instructions else "Generate a short-answer question."}

        [CONTEXT]
        {chunk.content}

        [TASK]
        1. Generate ONE question strictly based on the context.
        2. Adhere to the format, themes, and difficulty level specified above.
        3. If no format is specified, default to Short-Answer.
        4. If MCQ is requested, provide 4 options (A-D).

        [STRICT RETURN FORMAT]
        Question: <The question text and options if MCQ>
        Ideal Answer: <The correct answer key and explanation>
        """

        system_prompt = self.instructions if self.instructions else default_system

        print(f"DEBUG: Sending prompt to LLM for chunk {chunk.id}...")
        response_text = self.llm.generate_content(user_prompt, system_prompt=system_prompt)
        
        q_text, a_text = self._parse_ai_response(response_text)
        
        question = Question(
            question_text=q_text,
            ideal_answer=a_text,
            status=QuestionStatus.PENDING,
            chunk_id=chunk.id,
            subsection_id=subsection_id
        )
        self.db.add(question)
        self.db.commit()


    def _parse_ai_response(self, text: str):
        """Robust parser for AI-generated assessment content, handling markdown and flexible tagging."""
        import re
        
        # Look for "Question:" and "Ideal Answer:" even if inside markdown like **Question:**
        q_match = re.search(r"(?:Question|QUESTION)[:\s*]+(.*?)(?=(?:Ideal Answer|IDEAL ANSWER)|$)", text, re.DOTALL | re.IGNORECASE)
        a_match = re.search(r"(?:Ideal Answer|IDEAL ANSWER)[:\s*]+(.*)", text, re.DOTALL | re.IGNORECASE)
        
        q_text = q_match.group(1).strip() if q_match else None
        a_text = a_match.group(1).strip() if a_match else None
        
        if q_text and a_text:
            # Clean up residual markdown if any (like trailing ***)
            q_text = re.sub(r"\*\*+$", "", q_text).strip()
            a_text = re.sub(r"\*\*+$", "", a_text).strip()
            return q_text, a_text
            
        return "Failed to parse question.", "Consult source material."

