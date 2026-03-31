import re
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
        # Verify professor instructions are loaded
        instruction_source = "PROFESSOR_CUSTOM" if self.instructions \
            else "DEFAULT_FALLBACK"
        instruction_preview = (
            self.instructions[:80] + "..."
            if self.instructions and len(self.instructions) > 80
            else self.instructions or "using built-in default"
        )
        print(f"[ProfessorBot] Instructions source: {instruction_source}")
        print(f"[ProfessorBot] Preview: {instruction_preview}")
        print(f"[ProfessorBot] Turn: {turn_number} | "
              f"Phase: {phase} | Follow-up: {is_follow_up}")

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
        if self.instructions:
            base_instructions = self.instructions
        else:
            # Generic fallback — does not assume any subject domain
            base_instructions = """You are a rigorous academic examiner
conducting a 1-on-1 Socratic assessment based ONLY on the
uploaded course material.

Core rules:
- Ask exactly ONE question at a time. Never ask multiple questions.
    - **RULE: CONTENT INTEGRITY**: You are strictly prohibited from inventing questions that are NOT directly supported by the current context chunk. 
    - **RULE: HEADER/FOOTER SUPPRESSION**: If the provided context contains only generic information (e.g. "HKUST Business School", "Center for Case Studies") or looks like a logo or page number, YOU MUST NOT ask a question. Respond with exactly: "INSUFFICIENT_CONTEXT: I need a more factual section of the text for a question."
    - **RULE: NO-CROSS-LEAKAGE**: If the current instructions mention "300 Cubits", you are FORBIDDEN from mentioning "Valuation", "Imputed Multiples", or "Buildings" unless those exact words are in the provided context chunk. DO NOT use your memory of previous PDFs.
    - **RULE: SOURCE IS SUPREME**: Under no circumstances should you use your internal knowledge to supplement the documents. If the chunk is empty or useless, admit it.
- If the student says they do not know: ask what they DO remember
  from the material rather than moving on.

Tone: Professional, encouraging, intellectually rigorous."""

        print(f"[ProfessorBot] Using "
              f"{'custom' if self.instructions else 'generic fallback'}"
              f" instructions")
        
        system_prompt = f"""ROLE: You are a state-of-the-art academic examiner. 
You are conducting a 1-on-1 Socratic assessment for a student.

{"PRIMARY SYSTEM INSTRUCTIONS:" if self.instructions else "DEFAULT PEDAGOGY:"}
{base_instructions}

IMPORTANT: Your response MUST follow this exact structure:
Question: [Your question text here]
Ideal Answer: [A brief, 1-2 sentence expected answer here]

STRICT MANDATE: You MUST prioritize the PRIMARY SYSTEM INSTRUCTIONS above all else. 
If the instructions say 'be concise', do not write long paragraphs. 
If they say 'oral-friendly', avoid formulas that cannot be spoken.
"""

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

        BLOOM_INSTRUCTIONS = {
            1: "BLOOM PHASE 1 (Recall): Ask the student to define or identify a key term or fact from the text. Keep it direct.",
            2: "BLOOM PHASE 2 (Comprehension): Ask the student to explain or summarise a concept in their own words.",
            3: "BLOOM PHASE 3 (Application): Ask the student to apply a concept to a specific scenario or example.",
            4: "BLOOM PHASE 4 (Analysis): Ask the student to compare, differentiate, or examine relationships between concepts.",
            5: "BLOOM PHASE 5 (Synthesis): Ask the student to construct an argument, design a solution, or evaluate a position."
        }
        user_prompt += f"\n\n*** {BLOOM_INSTRUCTIONS.get(bloom_phase, BLOOM_INSTRUCTIONS[1])} ***"

        if is_follow_up:
             if phase == 2:
                 user_prompt += "\n\n*** CURRENT ARC: REMEDIAL FOLLOW-UP (Acknowledge & Probe) ***\nYou detected a CONCEPTUAL GAP. You MUST specifically acknowledge their last response (e.g., 'You mentioned [point]...') and then ask a probing 'Why' or 'How' question to help them bridge that specific gap. Do NOT move to a new topic yet. ***"
             elif phase == 3:
                 user_prompt += "\n\n*** CURRENT ARC: REMEDIAL CRITIQUE (Deep Dive) ***\nThe student is still struggling. Pivot to a critical reflection. Acknowledge their response, then ask where the logic they just discussed fails or what they might have overlooked in the text. ***"
             else:
                 user_prompt += "\n\n*** SPECIAL INSTRUCTION: You detected a CONCEPTUAL GAP. Acknowledge their mistake and ask a clarifying question. ***"
        else:
             # Regular Phased Flow (Always Phase 1 if no gap)
             user_prompt += f"\n\n*** CURRENT ARC: FRESH TOPIC (Basic Comprehension) ***\nAsk one sharp, independent question about a central theme or core concept from the reading by {author or 'the author'}. Do NOT feel forced to connect this to the previous answer if it was on a different topic. Start fresh."
             if turn_number == 1:
                 user_prompt += "\n\n*** SPECIAL INSTRUCTION: This is the first question of the assessment. Ask your question directly and immediately. Do NOT include any greeting. Begin with the question itself. ***"

        if misconception:
            user_prompt += f"\n\n*** MISCONCEPTION DETECTED: The student previously showed this gap: '{misconception}'. Generate a question that directly targets this specific gap to help them overcome it. ***"

        if concept_name:
            user_prompt += f"\n\n*** TARGET CONCEPT: Focus this question specifically on the concept: '{concept_name}'. ***"

        user_prompt += "\n\nSTRICT FINAL MANDATE: Study the CONVERSATION HISTORY carefully. "
        if is_follow_up:
            user_prompt += "\nCRITICAL: You are in a FOLLOW-UP mode. Your response MUST begin by acknowledging the student's previous point. Use a conversational bridge like 'You mentioned...' or 'Regarding your point about...'. DO NOT ignore the history. You must probe deeper into the logic of their previous answer."
        else:
            user_prompt += "\nFor this FRESH TOPIC turn, ensures you pick a NEW concept not previously discussed."

        user_prompt += "\n\nPlease generate the next question based on the reference material provided and following your system instructions."

        print(f"[ProfessorBot] System prompt length: {len(system_prompt)} chars")
        print(f"[ProfessorBot] User prompt length: {len(user_prompt)} chars")
        print(f"[ProfessorBot] Chunk ID: {chunk.id} | Chunk type: {chunk.chunk_type}")
        
        # Explicitly log adherence check to reassure user
        instruction_flag = "VERIFIED" if self.instructions else "USING_DEFAULT"
        print(f"[ProfessorBot] Pre-gen Instruction Check: {instruction_flag}")
        
        print(f"DEBUG: Generating question #{turn_number} for Chunk ID: {chunk.id} (Follow-up: {is_follow_up})")
        raw_text = LLMCallLogger.timed_call(
            caller="ProfessorBot",
            prompt=user_prompt,
            llm_fn=lambda: self.llm.generate_content(user_prompt, system_prompt=system_prompt),
            extra={"chunk_id": chunk.id, "turn": turn_number, "phase": phase}
        ).strip()
        
        # Parse the structured response
        q_text, a_text = self._parse_ai_response(raw_text, chunk)

        # --- Greeting extraction (turn 1 only) ---
        greeting = None
        if turn_number == 1 and q_text:
            try:
                # Detect if text starts with a greeting sentence
                greeting_pattern = re.compile(
                    r"^((?:Welcome|Hello|Good\s+\w+|Greetings|"
                    r"I(?:'m| am)\s+\w+|Let(?:'s| us)\s+get\s+started"
                    r"|It(?:'s| is)\s+\w+|I(?:'m| am)\s+delighted)"
                    r"[^?]*?\.\s*)",
                    re.IGNORECASE | re.DOTALL
                )
                match = greeting_pattern.match(q_text)
                if match:
                    greeting = match.group(1).strip()
                    # Remove greeting from question text
                    q_text = q_text[match.end():].strip()
                    # Clean up any remaining artifacts after stripping
                    q_text = re.sub(r"^\*+\s*", "", q_text).strip()
                    q_text = re.sub(
                        r"(?i)^question\s*[:\*]*\s*", "", q_text
                    ).strip()
                    print(f"[ProfessorBot] Greeting extracted: "
                          f"{greeting[:60]}...")
                    print(f"[ProfessorBot] Question after split: "
                          f"{q_text[:80]}...")
            except Exception as ge:
                print(f"[ProfessorBot] Greeting extraction failed: {ge}")
                greeting = None

        question = Question(
            question_text=q_text,
            ideal_answer=a_text,
            status=QuestionStatus.PENDING,
            chunk_id=chunk.id,
            subsection_id=chunk.subsection_id
        )
        # Store greeting as a non-mapped attribute
        # Frontend can read this from the API response
        # without needing a DB migration
        question._greeting = greeting

        self.db.add(question)
        self.db.commit()
        # Attach greeting to question object for API layer to use
        question.greeting = greeting
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
            # Step 1: Remove ALL asterisk clusters anywhere in text
            q_text = re.sub(r"\*+", " ", q_text)

            # Step 2: Remove ALL hash clusters at line start
            q_text = re.sub(r"(?m)^#+\s*", "", q_text)

            # Step 3: Remove QUESTION label in any form
            q_text = re.sub(
                r"(?i)(^\s*\*{0,3}\s*question\s*\*{0,3}\s*[:\-]?\s*)",
                "", q_text
            )

            # Step 4: Remove numbered prefixes like "1.", "1**", "1 -"
            q_text = re.sub(r"^\s*\d+[\.\*\-\s]+", "", q_text)

            # Step 5: Remove standalone section/chapter references
            q_text = re.sub(r"(?i)section\s*\d+(\.\d+)*", "", q_text)
            q_text = re.sub(r"(?i)chapter\s*\d+", "", q_text)

            # Step 6: Remove unknown author artifacts
            q_text = re.sub(r"(?i)\*\*unknown\*\*", "the author", q_text)
            q_text = re.sub(r"(?i)\bunknown\b", "the author", q_text)

            # Step 7: Collapse multiple spaces and strip
            q_text = re.sub(r"\s{2,}", " ", q_text).strip()

            # Safety net: strip any greeting the LLM added
            # despite being told not to
            try:
                greeting_pattern = re.compile(
                    r"^((?:Welcome|Hello|Good\s+\w+|Greetings|"
                    r"I(?:'m| am)\s+\w+|Let(?:'s| us)\s+get\s+started"
                    r"|It(?:'s| is)\s+a\s+pleasure|I(?:'m| am)\s+delighted|"
                    r"I(?:'m| am)\s+pleased|Thank\s+you\s+for)"
                    r"[^?]*?\.\s*)",
                    re.IGNORECASE | re.DOTALL
                )
                match = greeting_pattern.match(q_text)
                if match:
                    q_text = q_text[match.end():].strip()
                    print(f"[ProfessorBot] Safety net: stripped greeting "
                          f"from question text")
            except Exception as ge:
                print(f"[ProfessorBot] Greeting strip failed safely: {ge}")

            # Step 8: Ensure question ends with a question mark
            if q_text and not q_text.endswith("?"):
                if any(q_text.lower().startswith(w) for w in
                       ["what", "why", "how", "when", "where", "who",
                        "which", "explain", "describe", "define",
                        "compare", "analyse", "evaluate"]):
                    q_text = q_text.rstrip(".") + "?"

            if a_text:
                a_text = re.sub(r"\*+", " ", a_text)
                a_text = re.sub(r"(?m)^#+\s*", "", a_text)
                a_text = re.sub(
                    r"(?i)(^\s*ideal\s*answer\s*[:\-]?\s*)", "", a_text
                )
                a_text = re.sub(r"\s{2,}", " ", a_text).strip()

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

