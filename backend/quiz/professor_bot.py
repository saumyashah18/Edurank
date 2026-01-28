from typing import List, Dict
from sqlalchemy.orm import Session
from ..rag.embedder import RAGService
from ..database.models.chunk import ChunkType, Chunk
from ..database.models.question import Question, QuestionStatus
from ..database.models.transcript import Quiz
from ..database.models.hierarchy import Chapter, Section, Subsection
from .planner import TopicPlanner
from .llm_service import llm


class ProfessorBot:
    def __init__(self, db: Session, rag_service: RAGService, planner: TopicPlanner):
        self.db = db
        self.rag_service = rag_service
        self.planner = planner
        self.llm = llm
        self.instructions = None # To be fetched per course




    def generate_questions_for_course(self, course_id: int):
        """[DEPRECATED] Pool generation is now live. This returns a message indicating the system is ready."""
        return "Assessment Engine is Active: Questions are now generated live for each session."

    def _get_chapter_filters(self, instructions: str) -> List[str]:
        """Extracts chapter/unit numbers from instructions for filtering."""
        if not instructions:
            return None
            
        import re
        # Look for "Chapter X", "Unit X", "Ch X", "Chapter: X"
        patterns = [
            r"(?i)(?:chapter|unit|ch|module)[:\s]*(\d+)",
            r"(?i)only\s+from\s+(?:chapter|unit|ch|module)[:\s]*(\d+)"
        ]
        
        filters = []
        for p in patterns:
            found = re.findall(p, instructions)
            filters.extend(found)
            
        return list(set(filters)) if filters else None


    def generate_single_question(self, chunk: Chunk, author: str = None, student_struggled: bool = False, last_answer: str = None, progression_type: str = "FUNDAMENTAL"):
        """Generates ONE assessment question with optional struggle, reaction, and progression logic."""
        if not chunk:
            return None

        # 1. Graph-Aware Retrieval
        related_chunks = self._fetch_graph_relations(chunk.id)

        # 2. Assessment Generation
        return self._create_question_from_m_chunk(
            chunk, 
            author=author,
            related_chunks=related_chunks, 
            student_struggled=student_struggled, 
            last_answer=last_answer,
            progression_type=progression_type
        )

    def _fetch_graph_relations(self, chunk_id: int):
        """Fetches chunks connected via the deterministic KnowledgeRelation graph."""
        from ..database.models.chunk import Chunk, KnowledgeRelation, ChunkType
        relations = self.db.query(KnowledgeRelation).filter_by(source_id=chunk_id).limit(2).all()
        return [self.db.query(Chunk).get(rel.target_id) for rel in relations]

    def _create_question_from_m_chunk(self, chunk: Chunk, author: str = None, related_chunks: List[Chunk] = None, student_struggled: bool = False, last_answer: str = None, progression_type: str = "FUNDAMENTAL"):
        """Generates a question following structural assessment logic with conversational reaction."""
        
        graph_context = ""
        if related_chunks:
            graph_context = "\n### RELATED COMPARATIVE MATERIALS:\n"
            for rc in related_chunks:
                graph_context += f"- RELATED CONTENT: {rc.content[:500]}...\n"

        # 1. Minimal Prompt for Assessment Generation
        reaction_instruction = ""
        if last_answer:
            reaction_instruction = f"""
            ### DIALOGUE CONTEXT:
            The student's previous answer was: "{last_answer}"
            STRICT RULE: Begin your response by acknowledging and reacting to this specific answer in a professional yet conversational way. Do not just move to the next question.
            """

        author_display = author if author and author.lower() != "unknown" else "the author"
        
        if progression_type == "FUNDAMENTAL":
            progression_instruction = f"Begin by providing a brief, conversational conceptual setup that explains the core theme of this reading to meet the student halfway. Then, ask a SHARP, BROAD COMPREHENSION question about a central concept. YOU MUST MENTION THE AUTHOR ({author_display}) explicitly in the question."
        else:
            progression_instruction = "Briefly connect your follow-up to the student's previous point. Then, ask a question that probes a specific nuance of the reading. Do NOT repeat or rephrase the previous question."

        user_prompt = f"""
        MODE: Live Tutorial Assessment
        PROGRESSION: {progression_type}
        {reaction_instruction}
        
        [SOURCE MATERIAL]
        READING AUTHOR: {author_display}
        TOPIC: {chunk.subsection.section.title} > {chunk.subsection.title}
        CONTENT: {chunk.content}
        {graph_context}

        [INSTRUCTION]
        1. {progression_instruction}
        2. {"If the student is struggling or said 'I don't know', do not rephrase. Instead, ask a clarifying question about a simpler part of the same reading to help them re-engage." if student_struggled else ""}
        3. STRICTLY ONE QUESTION: Ask exactly one clear question at the end of your conversational setup.
        4. NO NUMERICAL REFERENCES: NEVER mention "page X", "chapter Y", "section Z.W", or "lines A-B". Use conceptual descriptions instead (e.g., "In the beginning of the argument..." or "When discussing the state...").
        5. CONVERSATIONAL SETUP: Do not just jump into the question. Explain the context or the 'why' behind the question in 1-2 sentences.
        
        ### OUTPUT FORMAT (MANDATORY):
        Question: [Your conversational reaction + context + the new question text]
        Ideal Answer: [A concise one-sentence summary of the correct answer]

        ### STYLE GUIDELINE:
        {self.instructions if self.instructions else "Standard academic tone."}
        """

        system_prompt = self.instructions if self.instructions else "You are an expert academic examiner."

        print(f"DEBUG: Generating assessment question for Chunk ID: {chunk.id} (Struggle: {student_struggled}, Progression: {progression_type})")
        raw_text = self.llm.generate_content(user_prompt, system_prompt=system_prompt).strip()
        
        # Parse the structured response
        q_text, a_text = self._parse_ai_response(raw_text)

        question = Question(
            question_text=q_text,
            ideal_answer=a_text,
            status=QuestionStatus.PENDING,
            chunk_id=chunk.id,
            subsection_id=chunk.subsection_id
        )
        self.db.add(question)
        self.db.commit()
        return question


    def _parse_ai_response(self, text: str):
        """Robust parser for AI-generated assessment content, handling DeepSeek R1 reasoning tags and markdown."""
        import re
        
        print(f"DEBUG: RAW AI Response:\n{text}\n{'='*30}")
        if not text or not text.strip():
            return "Could you tell me more about your thoughts on this reading?", "PENDING_STUDENT_RESPONSE"
            
        if text == "ERROR_RATE_LIMIT":
            return "The AI tutor is a bit busy right now (rate limit reached). Please wait a few seconds and try again.", "AI_RATE_LIMITED"
        # 0. Clean DeepSeek Reasoning/Think Tags
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        text = re.sub(r"<think>.*", "", text, flags=re.DOTALL).strip() # Handle unclosed tags
        
        # 1. Try to find Question and Ideal Answer using markers
        # We look for "Question:" and "Ideal Answer:" or similar variations
        q_patterns = [
            r"(?i)Question[:\s*]+(.*?)(?=(?:Ideal Answer|IDEAL ANSWER|Answer|ANSWER)|$)",
            r"(?i)\*\*Question:\*\*\s*(.*?)(?=(?:\*\*Ideal Answer:\*\*)|$)",
            r"(?i)1\.\s*Question:\s*(.*?)(?=2\.\s*Ideal Answer|$)"
        ]
        
        a_patterns = [
            r"(?i)(?:Ideal Answer|IDEAL ANSWER|Answer|ANSWER)[:\s*]+(.*)",
            r"(?i)\*\*Ideal Answer:\*\*\s*(.*)",
            r"(?i)2\.\s*Ideal Answer:\s*(.*)"
        ]
        
        q_text = None
        for p in q_patterns:
            match = re.search(p, text, re.DOTALL)
            if match and match.group(1).strip():
                q_text = match.group(1).strip()
                break
                
        a_text = None
        for p in a_patterns:
            match = re.search(p, text, re.DOTALL)
            if match and match.group(1).strip():
                a_text = match.group(1).strip()
                break

        # Fallback 1: If tags exist but are in common markdown list format without explicit labels
        if not q_text and "?" in text:
            # If there's an 'Ideal Answer' tag further down, split it
            if "ideal answer" in text.lower() or "answer:" in text.lower():
                parts = re.split(r"(?i)(?:Ideal Answer|Answer)[:\s*]+", text, maxsplit=1)
                if len(parts) == 2:
                    q_text = parts[0].strip()
                    a_text = parts[1].strip()
            else:
                # Assume the whole thing is the question if it's short
                if len(text) < 1000:
                    q_text = text.strip()
                    a_text = "CONSULT_SOURCE_MATERIAL"

        if q_text:
            # Clean up residual markdown (bolding tokens, hashes)
            q_text = re.sub(r"^\*\*+|^\#+|\*\*+$", "", q_text).strip()
            q_text = re.sub(r"(?i)^Question:\s*", "", q_text).strip()
            
            # STRIKE SECTION/CHAPTER NUMBERS (Fail-safe for user requirement)
            # Removes "Section 80.1", "Chapter 5", "lines 10-20", etc.
            q_text = re.sub(r"(?i)section\s*\d+(\.\d+)*", "", q_text)
            q_text = re.sub(r"(?i)chapter\s*\d+", "", q_text)
            q_text = re.sub(r"(?i)line[s]?\s*\d+([-]\d+)?", "", q_text)
            
            # STRIKE "unknown" author references
            q_text = re.sub(r"(?i)\*\*unknown\*\*", "the author", q_text)
            q_text = re.sub(r"(?i)unknown", "the author", q_text)
            
            q_text = re.sub(r"\s+", " ", q_text).strip() # Clean extra spaces

            if a_text:
                a_text = re.sub(r"^\*\*+|^\#+|\*\*+$", "", a_text).strip()
                a_text = re.sub(r"(?i)^Ideal Answer:\s*", "", a_text).strip()
            
            return q_text, a_text or "CONSULT_SOURCE_MATERIAL"
            
        # Fallback 2: Split by the first question mark if everything else fails
        if "?" in text:
             pos = text.find("?")
             return text[:pos+1].strip(), text[pos+1:].strip() if len(text) > pos+1 else "CONSULT_SOURCE_MATERIAL"

        return "I'm interested in hearing your perspective on this. Could you elaborate?", "PENDING_STUDENT_RESPONSE"
