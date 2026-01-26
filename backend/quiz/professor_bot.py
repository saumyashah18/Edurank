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

    def _extract_topic_filters(self, instructions: str) -> List[str]:
        """Extracts chapter numbers using RegEx (saves tokens) or Gemini as fallback."""
        if not instructions or len(instructions) < 5:
            return None
            
        import re
        # Try simple RegEx first for "Chapter X" or "Unit X"
        chapters = re.findall(r"(?i)chapter\s*(\d+)", instructions)
        if chapters:
            return [f"Chapter {c}" for c in chapters]
            
        # Optional: Add more RegEx patterns or just return None for now to be safe
        # We'll skip the LLM call for every request to save quota.
        return None

    def generate_single_question(self, course_id: int, history: List[Dict[str, str]] = None, is_simulation: bool = True, student_name: str = None):
        """Generates ONE question grounded in the chunk, adapted to student history if provided."""
        
        # 0. Extract Filters from Instructions (RegEx only now)
        quiz_config = self.db.query(Quiz).filter_by(course_id=course_id).order_by(Quiz.id.desc()).first()
        self.instructions = quiz_config.instructions if quiz_config else None
        filters = self._extract_topic_filters(self.instructions)
        
        # 1. Turn Detection & Topic Selection
        history_len = len(history) if history else 0
        turn_count = history_len + 1
        
        # 2. Topic Selection with Diversity & Filtering
        # We let the instructions (system prompt) guide the starting point/arc.
        topic = self.planner.select_next_topic(course_id, student_id=None, history=history, filter_keywords=filters)
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
        
        # 3. Optional Comparison Chunk (The 'Compendium Linkage')
        # We always try to provide one to the LLM if available, 
        # allowing it to follow the "bridge two readings" instruction if requested.
        comparison_chunk = self._fetch_comparison_chunk(course_id, exclude_subsection_id=topic["subsection_id"])

        # 4. Generation: Strictly Instruction-Led
        return self._create_question_from_m_chunk(m_chunk, topic["subsection_id"], history, comparison_chunk, related_chunks, turn_count, is_simulation=is_simulation, student_name=student_name)

    def _fetch_graph_relations(self, chunk_id: int):
        """Fetches chunks connected via explicit KnowledgeRelation graph."""
        from ..database.models.chunk import KnowledgeRelation
        relations = self.db.query(KnowledgeRelation).filter_by(source_id=chunk_id).limit(2).all()
        return [self.db.query(Chunk).get(rel.target_id) for rel in relations]

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

    def _create_question_from_m_chunk(self, chunk: Chunk, subsection_id: int, history: List[Dict[str, str]] = None, comparison_chunk: Chunk = None, related_chunks: List[Chunk] = None, turn_count: int = 1, is_simulation: bool = True, student_name: str = None):
        """Generates a question following structural or conversational logic."""
        
        # Build history context
        history_context = ""
        if history:
            history_context = "\n### DIALOGUE SO FAR:\n"
            for turn in history[-4:]: 
                history_context += f"AI: {turn.get('q')}\nSTUDENT: {turn.get('a')}\n---\n"

        comparison_context = ""
        if comparison_chunk:
            comparison_context = f"\n### SECONDARY AUTHOR/CONTEXT (For Connection/Bridge):\n{comparison_chunk.content}\n"

        graph_context = ""
        if related_chunks:
            graph_context = "\n### KNOWLEDGE GRAPH RELATIONS (Connected Concepts):\n"
            for rc in related_chunks:
                graph_context += f"- RELATED CONCEPT: {rc.content[:200]}...\n"

        # 5. Detect recently used themes to avoid repetition
        used_themes = []
        if history:
            all_text = " ".join([turn.get('q', '') for turn in history])
            # Expanded list of authors/themes based on syllabus ingestion
            syllabus_themes = ["YouTube", "Chatterjee", "Said", "Scott", "Held", "Anderson", "Fanon", "Facebook", "Globalization"]
            for theme in syllabus_themes:
                if theme.lower() in all_text.lower():
                    used_themes.append(theme)
        
        avoid_instruction = ""
        if used_themes:
            avoid_instruction = f"AVOID REPEATING THESE THEMES (Recently discussed): {', '.join(used_themes)}. Explore OTHER aspects of the syllabus unless specifically directed by the user's system instructions to stay on a topic."

        # MODE-SPECIFIC PROMPT
        if not is_simulation:
            # POOL GENERATION MODE: Needs structural parsing
            prompt_goal = "Generate a sharp assessment question and an ideal answer based on the material."
            additional_constraints = "FORMAT: Question: [text] Ideal Answer: [short sentence summary]."
        else:
            # SIMULATION MODE: Conversational
            prompt_goal = f"Respond as the Professor. Current Turn: {turn_count}."
            additional_constraints = "Do NOT provide an 'Ideal Answer'. Simply speak to the student."

        # REFINED BRIDGING LOGIC: Use KnowledgeRelations if they exist
        relation_hint = ""
        if related_chunks and turn_count > 1:
            from ..database.models.chunk import KnowledgeRelation
            rel = self.db.query(KnowledgeRelation).filter(
                (KnowledgeRelation.source_id == chunk.id) & 
                (KnowledgeRelation.target_id.in_([rc.id for rc in related_chunks]))
            ).first()
            if rel:
                relation_hint = f"\n### CONCEPTUAL LINK (Knowledge Graph):\nThe primary material HAS a '{rel.relation_type}' relationship with the related concepts. You MUST test the student on this specific link."

        user_prompt = f"""
        [ADAPTIVE CONTEXT]
        TURN_COUNT: {turn_count}
        {avoid_instruction}
        IS_START_OF_CONVERSATION: {bool(turn_count == 1)}
        MODE: {"Simulation" if is_simulation else "Pool Generation"}
        
        [SOURCE MATERIALS]
        PRIMARY (The focus): {chunk.content}
        {comparison_context}
        {graph_context}
        {relation_hint}

        [CONVERSATION HISTORY]
        {history_context}

        [INSTRUCTION]
        {prompt_goal}
        {additional_constraints}
        
        If bridging or multiple topics are present, do NOT ask about them separately. 
        Create a single, synthetic question that forces the student to connect these ideas.
        
        STRICTLY follow your system instructions for tone, behavior, and structural goals.
        Ground your response in the provided [SOURCE MATERIALS].
        """

        default_persona = f"""
        You are an elite academic examiner for "Dialogue box". Your goal is to conduct a deep, conversational assessment.
        
        STRICT RULES:
        1. NO ANSWERS: Never give the student the actual answer, even if they ask or fail repeatedly. 
        2. GUIDANCE: If a student is stuck or partially correct, provide a subtle hint or a Socratic follow-up question to lead them to the truth.
        3. TONE: Be professional, encouraging, and intellectual.
        {f"4. GREETING: This is the very first turn. Start by saying 'Hi {student_name}!' followed by an introduction and your first question." if turn_count == 1 and student_name else ""}
        5. CONVERSATION: If turn_count > 1, respond naturally to their last answer before moving to the next point or providing a hint.
        """

        system_prompt = self.instructions if self.instructions else default_persona

        print(f"DEBUG: Generation Mode: {'Simulation' if is_simulation else 'Pool'} | Turn: {turn_count}")
        raw_text = self.llm.generate_content(user_prompt, system_prompt=system_prompt).strip()
        
        q_text, a_text = raw_text, "SOURCE_MATERIAL_REFERENCE"
        
        if not is_simulation:
            # Parse the structured response
            q_text, a_text = self._parse_ai_response(raw_text)

        question = Question(
            question_text=q_text,
            ideal_answer=a_text,
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
        
        # Improved Regex: Handles Question/QUESTION followed by Answer/Ideal Answer in various formats
        q_match = re.search(r"(?:\*\*|#)?\s*(?:Question|QUESTION)[:\s*]+(.*?)(?=(?:\*\*|#)?\s*(?:Ideal Answer|IDEAL ANSWER|Answer|ANSWER)|$)", text, re.DOTALL | re.IGNORECASE)
        a_match = re.search(r"(?:\*\*|#)?\s*(?:Ideal Answer|IDEAL ANSWER|Answer|ANSWER)[:\s*]+(.*)", text, re.DOTALL | re.IGNORECASE)
        
        q_text = q_match.group(1).strip() if q_match else None
        a_text = a_match.group(1).strip() if a_match else None
        
        # Fallback: If no tags found but it's a short response, assume it's just the question
        if not q_text and len(text) < 500:
            return text, "SOURCE_MATERIAL_REFERENCE"

        if q_text and a_text:
            # Clean up residual markdown if any
            q_text = re.sub(r"\*\*+$", "", q_text).strip()
            a_text = re.sub(r"\*\*+$", "", a_text).strip()
            return q_text, a_text
            
        return "Failed to parse question.", "Consult source material."

