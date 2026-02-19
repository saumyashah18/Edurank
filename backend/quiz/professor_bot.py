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


    def generate_single_question(self, chunk: Chunk, course_id: int = None, author: str = None, student_struggled: bool = False, history_turns: List[Dict[str, str]] = None):
        """Generates ONE assessment question. System instructions drive all behavior."""
        if not chunk:
            return None

        # Feedback context from likes/dislikes (optional enrichment)
        feedback_examples = ""
        if course_id:
            feedback_examples = self._get_feedback_context(course_id)

        return self._create_question_from_m_chunk(
            chunk, 
            author=author,
            history_turns=history_turns,
            feedback_examples=feedback_examples
        )

    def _get_feedback_context(self, course_id: int) -> str:
        """Fetches upvoted and downvoted questions to reinforce the teacher's style preferences."""
        from ..database.models.question import Question
        from ..database.models.hierarchy import Subsection
        
        liked = self.db.query(Question).join(Subsection).filter(Question.upvotes > 0).order_by(Question.id.desc()).limit(5).all()
        disliked = self.db.query(Question).join(Subsection).filter(Question.downvotes > 0).order_by(Question.id.desc()).limit(5).all()
        
        context = ""
        if liked:
            context += "\nTeacher liked these question styles:\n"
            for q in liked:
                context += f"- \"{q.question_text}\"\n"
        
        if disliked:
            context += "\nTeacher disliked these question styles (avoid):\n"
            for q in disliked:
                context += f"- \"{q.question_text}\"\n"
                
        return context

    def _fetch_graph_relations(self, chunk_id: int):
        """Fetches chunks connected via the deterministic KnowledgeRelation graph."""
        from ..database.models.chunk import Chunk, KnowledgeRelation, ChunkType
        relations = self.db.query(KnowledgeRelation).filter_by(source_id=chunk_id).limit(2).all()
        return [self.db.query(Chunk).get(rel.target_id) for rel in relations]

    def _create_question_from_m_chunk(self, chunk: Chunk, author: str = None, history_turns: List[Dict[str, str]] = None, feedback_examples: str = ""):
        """
        Generates a question. The professor's system instructions are the SOLE system prompt.
        No hardcoded phases, greetings, or topic rotation logic — all of that is in the instructions.
        """
        
        author_display = author if author and author.lower() != "unknown" else "the author"

        # --- SYSTEM PROMPT: Professor's instructions ONLY, unmodified ---
        system_prompt = self.instructions if self.instructions else "You are an expert academic examiner. Ask one sharp question at a time about the provided reading material."

        # --- USER PROMPT: Conversation history + source material + output format ---
        # Build conversation history
        history_block = ""
        if history_turns:
            history_block = "CONVERSATION SO FAR:\n"
            for turn in history_turns:
                role_label = "EXAMINER" if turn['role'] == 'bot' else "STUDENT"
                history_block += f"{role_label}: {turn['text']}\n"
            history_block += "\n"

        user_prompt = f"""{history_block}{feedback_examples}
READING AUTHOR: {author_display}
TOPIC: {chunk.subsection.section.title} > {chunk.subsection.title}
SOURCE MATERIAL:
{chunk.content}

Respond in this format:
Question: [Your question]
Ideal Answer: [Brief expected answer]"""

        print(f"DEBUG: Generating question for Chunk ID: {chunk.id}, Author: {author_display}, History turns: {len(history_turns) if history_turns else 0}")
        raw_text = self.llm.generate_content(user_prompt, system_prompt=system_prompt).strip()
        
        # Parse the structured response
        q_text, a_text = self._parse_ai_response(raw_text, chunk)

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


    def _parse_ai_response(self, text: str, chunk: Chunk = None):
        """Robust parser for AI-generated assessment content."""
        import re
        
        print(f"DEBUG: RAW AI Response:\n{text}\n{'='*30}")
        if not text or not text.strip():
            # Fallback uses the actual chunk content instead of a vague question
            author = self.planner.get_chunk_author(chunk) if chunk else "the author"
            return f"What is the central argument {author} makes in this reading?", "CONSULT_SOURCE_MATERIAL"
            
        if text == "ERROR_RATE_LIMIT":
            return "The AI tutor is a bit busy right now (rate limit reached). Please wait a few seconds and try again.", "AI_RATE_LIMITED"

        if text.startswith("ERROR:"):
            return "I'm having a brief technical connection issue. Please try your response again, or click 'Refetch' to try a new question.", "AI_ERROR"

        # Clean DeepSeek Reasoning/Think Tags
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        text = re.sub(r"<think>.*", "", text, flags=re.DOTALL).strip()
        
        # Try to find Question and Ideal Answer using markers
        q_patterns = [
            r"(?i)Question[:\s*]+(.*?)(?=(?:Ideal Answer|IDEAL ANSWER|Answer|ANSWER)|$)",
            r"(?i)\*\*Question:\*\*\s*(.*?)(?=(?:\*\*Ideal Answer:\*\*)|$)",
        ]
        
        a_patterns = [
            r"(?i)(?:Ideal Answer|IDEAL ANSWER|Answer|ANSWER)[:\s*]+(.*)",
            r"(?i)\*\*Ideal Answer:\*\*\s*(.*)",
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
        
        # Fallback: If no explicit labels but contains a question mark
        if not q_text and "?" in text:
            if "ideal answer" in text.lower() or "answer:" in text.lower():
                parts = re.split(r"(?i)(?:Ideal Answer|Answer)[:\s*]+", text, maxsplit=1)
                if len(parts) == 2:
                    q_text = parts[0].strip()
                    a_text = parts[1].strip()
            else:
                q_text = text.strip()
                a_text = "CONSULT_SOURCE_MATERIAL"
        
        if q_text:
            # Clean up markdown artifacts
            q_text = re.sub(r"^\*\*+|^\#+|\*\*+$", "", q_text).strip()
            q_text = re.sub(r"(?i)^Question:\s*", "", q_text).strip()
            q_text = re.sub(r"(?i)section\s*\d+(\.\d+)*", "", q_text)
            q_text = re.sub(r"(?i)chapter\s*\d+", "", q_text)
            q_text = re.sub(r"(?i)line[s]?\s*\d+([-]\d+)?", "", q_text)
            q_text = re.sub(r"(?i)\*\*unknown\*\*", "the author", q_text)
            q_text = re.sub(r"(?i)unknown", "the author", q_text)
            q_text = re.sub(r"\s+", " ", q_text).strip()
            
            if a_text:
                a_text = re.sub(r"^\*\*+|^\#+|\*\*+$", "", a_text).strip()
                a_text = re.sub(r"(?i)^Ideal Answer:\s*", "", a_text).strip()
            
            return q_text, a_text or "CONSULT_SOURCE_MATERIAL"
            
        # Last fallback: split by question mark
        if "?" in text:
             pos = text.find("?")
             return text[:pos+1].strip(), text[pos+1:].strip() if len(text) > pos+1 else "CONSULT_SOURCE_MATERIAL"
        
        # Final fallback: use chunk-aware question instead of vague generic
        author = self.planner.get_chunk_author(chunk) if chunk else "the author"
        return f"What is the central argument {author} makes in this reading?", "CONSULT_SOURCE_MATERIAL"

