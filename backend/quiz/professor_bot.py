from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from ..rag.embedder import RAGService
from ..database.models.chunk import ChunkType, Chunk
from ..database.models.question import Question, QuestionStatus
from ..database.models.transcript import Quiz
from ..database.models.hierarchy import Chapter, Section, Subsection
from .planner import TopicPlanner
from .llm_service import llm
from ..utils.llm_logger import LLMCallLogger


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


    def generate_single_question(self, chunk: Chunk, course_id: Optional[int] = None, author: Optional[str] = None, student_struggled: bool = False, history_turns: Optional[List[Dict[str, str]]] = None, turn_number: int = 1, is_follow_up: bool = False, phase: int = 1, bloom_phase: int = 1, misconception: Optional[str] = None, concept_name: Optional[str] = None):
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
            feedback_examples=feedback_examples,
            turn_number=turn_number,
            is_follow_up=is_follow_up,
            phase=phase,
            bloom_phase=bloom_phase,
            misconception=misconception,
            concept_name=concept_name
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

    def get_related_chunk(self, chunk_id: int):
        """Fetches a related chunk connected via the KnowledgeRelation graph."""
        from ..database.models.chunk import Chunk, KnowledgeRelation
        # Try to find a 'Prerequisite' or 'Related' chunk
        relation = self.db.query(KnowledgeRelation).filter_by(source_id=chunk_id).first()
        if relation:
            return self.db.query(Chunk).get(relation.target_id)
        return None

    def _create_question_from_m_chunk(self, chunk: Chunk, author: Optional[str] = None, history_turns: Optional[List[Dict[str, str]]] = None, feedback_examples: str = "", turn_number: int = 1, is_follow_up: bool = False, phase: int = 1, bloom_phase: int = 1, misconception: Optional[str] = None, concept_name: Optional[str] = None):
        """
        Generates a question. The professor's system instructions are the SOLE system prompt.
        We append the required output format to the system prompt to ensure structured responses.
        """

        # --- SYSTEM PROMPT: Professor's instructions + Format requirement ---
        base_instructions = self.instructions if self.instructions else """Role: You are a rigorous, sharp Social Science Professor and Interlocutor. Your goal is to conduct a 1-on-1 Socratic examination based ONLY on the uploaded readings.

Core Constraints:
- One Question Only: Never ask "joint" or composite questions. Ask exactly one sharp question.
- No Direct Answers: If asked for the answer, point to a theme/section.
- Brevity: Keep every response under 3 sentences. Be punchy and academic.
- Handling Rudeness: If a student is dismissive, say: "We are here to engage with the material. If you are ready to return to the text, let’s look at [Author]."
- The "Stuck" Protocol: If a student says "I don't know", "I'm stuck", or gives an answer that shows they clearly don't remember a specific point, DO NOT STAY STUCK. You MUST ask a question directed exactly at this specific reading/text to see what they DO remember from this exact text itself. You MUST reply with exactly this phrase (or similar): "Do you remember any other part of [Author]’s argument from this specific reading, and why was that significant to you?"

The Conversation Arc (Strict Sequence):
- Phase 1 (Comprehension): Ask one sharp question about a central theme/core concept.
- Phase 2 (Reflection - Conversational Follow-up): You MUST acknowledge what the student just said. Start your question naturally like "Yes, you mentioned [X], but why does..." or "Building on your point about [Y]..."
- Phase 3 (Critique - Conversational Follow-up): You MUST acknowledge what the student just said. Ask: "Where does this logic fail in a contemporary context?" or "What does this author overlook?"

Tone: Conversational but academic, professional, provocative, and strictly intellectual. You are talking WITH the student, not AT them.
"""
        
        system_prompt = f"""{base_instructions}

IMPORTANT: You MUST respond in this exact format:
Question: [Your question text here]
Ideal Answer: [A brief, 1-2 sentence expected answer here]"""

        # --- User Prompt: Pure context and material ---
        history_block = ""
        if history_turns:
            history_block = "### CONVERSATION HISTORY (DO NOT REPEAT THESE QUESTIONS)\n"
            for turn in history_turns:
                role_label = "EXAMINER" if turn['role'] == 'bot' else "STUDENT"
                history_block += f"{role_label}: {turn['text']}\n"
            history_block += "\n"

        user_prompt = f"""Assessment Progress: Question #{turn_number}
{history_block}
### REFERENCE MATERIAL FOR THIS QUESTION
{chunk.content}

{feedback_examples}"""

        if is_follow_up:
             user_prompt += "\n\n*** SPECIAL INSTRUCTION: You detected a CONCEPTUAL GAP in the student's previous answer. Instead of moving to a new concept, please ask a clarifying or probing follow-up question to help the student overcome this specific gap. ***"
        else:
             # Regular Phased Flow
             if phase == 1:
                 user_prompt += f"\n\n*** CURRENT ARC: PHASE 1 (Basic Comprehension) ***\nAsk one sharp question about a central theme or core concept from the provided reading by {author or 'the author'}."
                 if turn_number == 1:
                     user_prompt += "\n\n*** SPECIAL INSTRUCTION: Since this is the very first question of the assessment, please start your response with a brief, professional welcoming greeting before asking the question. ***"
             elif phase == 2:
                 user_prompt += f"\n\n*** CURRENT ARC: PHASE 2 (Reflection - Follow-up) ***\nCRITICAL: You MUST specifically construct your question derived directly and exclusively from the student's PREVIOUS ANSWER. DO NOT ask a disconnected question from the reading. Start your question in a conversational manner acknowledging their exact point. For example, 'Yes, so you mentioned [their exact point], then how does [author] explain...'. Probe deeper into the 'Why' behind the specific logic or argument the student just mentioned regarding {author or 'the author'}."
             elif phase == 3:
                 user_prompt += f"\n\n*** CURRENT ARC: PHASE 3 (Critique - Follow-up) ***\nCRITICAL: You MUST specifically construct your question derived directly and exclusively from the student's PREVIOUS ANSWER. DO NOT ask a disconnected question. Start your question in a conversational manner acknowledging their exact point. Pivot to critical reflection based on their last response. Ask where the logic they just discussed fails in a contemporary context or what {author or 'the author'} overlooks."

        BLOOM_INSTRUCTIONS = {
            1: "BLOOM PHASE 1 (Recall): Ask the student to define or identify a key term or fact from the text. Keep it direct.",
            2: "BLOOM PHASE 2 (Comprehension): Ask the student to explain or summarise a concept in their own words.",
            3: "BLOOM PHASE 3 (Application): Ask the student to apply a concept to a specific scenario or example.",
            4: "BLOOM PHASE 4 (Analysis): Ask the student to compare, differentiate, or examine relationships between concepts.",
            5: "BLOOM PHASE 5 (Synthesis): Ask the student to construct an argument, design a solution, or evaluate a position."
        }
        user_prompt += f"\n\n*** {BLOOM_INSTRUCTIONS.get(bloom_phase, BLOOM_INSTRUCTIONS[1])} ***"

        if misconception:
            user_prompt += f"\n\n*** MISCONCEPTION DETECTED: The student previously showed this gap: '{misconception}'. Generate a question that directly targets this specific gap to help them overcome it. ***"

        if concept_name:
            user_prompt += f"\n\n*** TARGET CONCEPT: Focus this question specifically on the concept: '{concept_name}'. ***"

        user_prompt += "\n\nCRITICAL: Study the CONVERSATION HISTORY carefully. For Phase 1, ensure you pick a NEW concept not previously discussed. For Phases 2 and 3, ensure you are directly following up on the student's immediate previous answer using a conversational tone."
        user_prompt += "\n\nPlease generate the next question based on the reference material provided and following your system instructions."

        print(f"DEBUG: Generating question #{turn_number} for Chunk ID: {chunk.id} (Follow-up: {is_follow_up})")
        raw_text = LLMCallLogger.timed_call(
            caller="ProfessorBot",
            prompt=user_prompt,
            llm_fn=lambda: self.llm.generate_content(user_prompt, system_prompt=system_prompt),
            extra={"chunk_id": chunk.id, "turn": turn_number, "phase": phase}
        ).strip()
        
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

    def generate_hint(self, question_text: str, chunk_content: str, misconception: Optional[str] = None) -> str:
        """
        Generates a Socratic hint when student score < 0.4.
        Hint guides toward the answer without giving it away.
        """
        system_prompt = """You are a Socratic tutor. Generate a hint that guides the student
        toward the answer WITHOUT revealing it. Use a question or a clue.
        Keep it to 1-2 sentences. Be encouraging but intellectually challenging."""

        user_prompt = f"""The student is struggling with this question:
        QUESTION: {question_text}
        REFERENCE MATERIAL: {chunk_content[:500]}
        """
        if misconception:
            user_prompt += f"\nKNOWN GAP: {misconception}"
        user_prompt += "\n\nGenerate a Socratic hint (1-2 sentences, no direct answer):"

        hint = LLMCallLogger.timed_call(
            caller="ProfessorBot.hint",
            prompt=user_prompt,
            llm_fn=lambda: self.llm.generate_content(user_prompt, system_prompt=system_prompt),
            extra={"has_misconception": misconception is not None}
        )
        if not hint or hint.startswith("ERROR"):
            return "Think about the core argument the author is making. What evidence do they use to support it?"
        return hint.strip()

    def generate_follow_up(
        self,
        chunk: Chunk,
        history_turns: list,
        last_score: float,
        misconception: Optional[str] = None,
        bloom_phase: int = 1,
        concept_name: Optional[str] = None
    ) -> Question:
        """
        Generates a targeted follow-up question based on last answer quality.
        - score < 0.4: probing question targeting misconception
        - 0.4 <= score < 0.8: consolidating question on same concept
        - score >= 0.8: deeper question advancing Bloom's phase
        """
        if last_score < 0.4:
            is_follow_up = True
            next_phase = bloom_phase  # Stay at same phase
        elif last_score < 0.8:
            is_follow_up = True
            next_phase = bloom_phase  # Consolidate
        else:
            is_follow_up = False
            next_phase = min(5, bloom_phase + 1)  # Advance phase

        return self.generate_single_question(
            chunk=chunk,
            history_turns=history_turns,
            is_follow_up=is_follow_up,
            bloom_phase=next_phase,
            misconception=misconception if last_score < 0.4 else None,
            concept_name=concept_name,
            turn_number=len(history_turns) + 1
        )

