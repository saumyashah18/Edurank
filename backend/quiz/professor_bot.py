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
            # Pass is_simulation=False to ensure we generate actual questions for the pool
            question = self.generate_single_question(course_id, is_simulation=False)
            if question:
                total_generated += 1
                processed_subsections.append(question.subsection_id)
        
        return f"Pool Ready: Generated {total_generated} diverse questions for the assessment."

    def generate_single_question(self, course_id: int, history: List[Dict[str, str]] = None, is_simulation: bool = True):
        """Generates ONE question grounded in the chunk, adapted to student history if provided."""
        print(f"DEBUG: generate_single_question - is_simulation: {is_simulation}, history_len: {len(history) if history else 0}")
        # Phase 0: Introduction & Preference
        # Only trigger for simulations with no history
        if is_simulation and (not history or len(history) < 1):
            print("DEBUG: generate_single_question -> Phase 0 Greeting")
            return self._generate_opening_greeting(course_id)

        # 1. Phase Detection & Topic Selection
        history_len = len(history) if history else 0
        current_phase = self._determine_phase(history_len)
        
        # 2. Topic Selection with Diversity
        topic = self.planner.select_next_topic(course_id, student_id=None, history=history)
        if not topic:
            return None

        # Primary Chunk
        m_chunk = self.db.query(Chunk).filter_by(
            subsection_id=topic["subsection_id"],
            chunk_type=ChunkType.MEDIUM
        ).first()

        if not m_chunk:
            return None

        # Graph-Aware Retrieval (Knowledge Relations)
        related_chunks = self._fetch_graph_relations(m_chunk.id)
        
        # 3. Optional Comparison Chunk (Mandatory in Phase 2 for Diversity)
        comparison_chunk = None
        if current_phase == "PHASE_2_CONNECTION":
            comparison_chunk = self._fetch_comparison_chunk(course_id, exclude_subsection_id=topic["subsection_id"])

        # 4. Generation with Phase Awareness
        return self._create_question_from_m_chunk(m_chunk, topic["subsection_id"], history, comparison_chunk, related_chunks, current_phase)

    def _determine_phase(self, history_len: int):
        """Maps history length to the user's requested conversation arc."""
        if history_len <= 3:
            return "PHASE_1_COMPREHENSION"
        elif history_len <= 6:
            return "PHASE_2_CONNECTION"
        else:
            return "PHASE_3_CRITIQUE"

    def _fetch_graph_relations(self, chunk_id: int):
        """Fetches chunks connected via explicit KnowledgeRelation graph."""
        from ..database.models.chunk import KnowledgeRelation
        relations = self.db.query(KnowledgeRelation).filter_by(source_id=chunk_id).limit(2).all()
        return [self.db.query(Chunk).get(rel.target_id) for rel in relations]

    def _generate_opening_greeting(self, course_id: int):
        """Generates a conversational opening asking for student interest."""
        # We don't save this as a 'Question' in DB yet, or we save it as a meta-question
        # For simplicity, let's return a dummy question object or just the text
        q_text = "Hello! I'm your examiner for this course. Before we dive into the material, which author or specific topic from the syllabus did you find most compelling or challenging?"
        
        question = Question(
            question_text=q_text,
            ideal_answer="WAITING_FOR_PREFERENCE",
            status=QuestionStatus.PENDING,
            chunk_id=None,
            subsection_id=None
        )
        self.db.add(question)
        self.db.commit()
        return question

    def _detect_author_preference(self, history: List[Dict[str, str]]):
        """Simple heuristic to detect author names in early history."""
        # For now, just look for common names if the history is 1 turn deep
        if not history: return None
        first_user_msg = history[0].get('a', '').lower()
        # This could be expanded with a list of authors from DB metadata
        return None 

    def _fetch_comparison_chunk(self, course_id: int, exclude_subsection_id: int):
        """Fetches a chunk from a different part of the syllabus for comparison."""
        comparison_topic = self.planner.select_next_topic(course_id, student_id=None)
        if comparison_topic and comparison_topic["subsection_id"] != exclude_subsection_id:
            return self.db.query(Chunk).filter_by(
                subsection_id=comparison_topic["subsection_id"],
                chunk_type=ChunkType.MEDIUM
            ).first()
        return None

    def _create_question_from_m_chunk(self, chunk: Chunk, subsection_id: int, history: List[Dict[str, str]] = None, comparison_chunk: Chunk = None, related_chunks: List[Chunk] = None, phase: str = "PHASE_1_COMPREHENSION"):
        """Generates a question following Coursera-style adaptive dialogue logic."""
        
        # Build history context
        history_context = ""
        if history:
            history_context = "\n### DIALOGUE SO FAR:\n"
            for turn in history[-4:]: 
                history_context += f"AI: {turn.get('q')}\nSTUDENT: {turn.get('a')}\n---\n"

        comparison_context = ""
        if comparison_chunk:
            comparison_context = f"\n### SECONDARY AUTHOR/CONTEXT (For PH2 Connection):\n{comparison_chunk.content}\n"

        graph_context = ""
        if related_chunks:
            graph_context = "\n### KNOWLEDGE GRAPH RELATIONS (Connected Concepts):\n"
            for rc in related_chunks:
                graph_context += f"- RELATED CONCEPT: {rc.content[:200]}...\n"

        # 5. Detect recently used themes to avoid repetition
        used_themes = []
        if history:
            all_text = " ".join([turn.get('q', '') for turn in history])
            for theme in ["YouTube", "Anderson", "Facebook", "Globalization"]:
                if theme.lower() in all_text.lower():
                    used_themes.append(theme)
        
        avoid_instruction = ""
        if used_themes:
            avoid_instruction = f"AVOID REPEATING THESE THEMES: {', '.join(used_themes)} unless essential."

        user_prompt = f"""
        [ADAPTIVE CONTEXT]
        PHASE: {phase}
        {avoid_instruction}
        
        [SOURCE MATERIALS]
        PRIMARY: {chunk.content}
        {comparison_context}
        {graph_context}

        [CONVERSATION HISTORY]
        {history_context}

        [INSTRUCTION]
        You are in {phase}. 
        Following your system instructions, generate the next Professor response. 
        Focus strictly on the syllabus material and do not repeat themes already discussed.
        """

        system_prompt = self.instructions if self.instructions else "You are an examiner. Generate a sharp, short-answer question based on the material."

        print(f"DEBUG: Adaptive Generation for chunk {chunk.id} (Comparison: {bool(comparison_chunk)})")
        q_text = self.llm.generate_content(user_prompt, system_prompt=system_prompt).strip()
        
        # NO MORE hardcoded transitions here. Let the persona handle it.

        question = Question(
            question_text=q_text,
            ideal_answer="SOURCE_MATERIAL_REFERENCE",
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

