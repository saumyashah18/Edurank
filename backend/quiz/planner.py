from sqlalchemy.orm import Session
from ..database.models.hierarchy import Chapter, Section, Subsection
from ..database.models.transcript import Transcript

class TopicPlanner:
    def __init__(self, db: Session):
        self.db = db

    def select_next_topic(self, course_id: int, enrollment_id: str = None, quiz_id: int = None, filter_keywords: list = None, used_chunk_ids: list = None, preferred_section_id: int = None):
        """
        Selects the next chunk to ask a question about.
        Rotates across DIFFERENT SECTIONS of the syllabus to ensure topic variety.
        Uses enrollment_id as seed so each student gets a different order.
        """
        import random
        import hashlib
        from ..database.models.transcript import Transcript
        from ..database.models.question import Question
        from ..database.models.chunk import Chunk, ChunkType

        # 1. Identify used Chunk IDs and used Section IDs
        if used_chunk_ids is None:
            used_chunk_ids = []
            
        used_section_ids = set()
        if enrollment_id and quiz_id:
            used_data = self.db.query(Question.chunk_id, Chunk.subsection_id).join(
                Chunk, Question.chunk_id == Chunk.id
            ).join(
                Transcript, Transcript.question_id == Question.id
            ).filter(
                Transcript.enrollment_id == enrollment_id, 
                Transcript.quiz_id == quiz_id
            ).all()
            
            for chunk_id, subsection_id in used_data:
                used_chunk_ids.append(chunk_id)
                # Track the SECTION (parent of subsection) as "used"
                subsection = self.db.query(Subsection).get(subsection_id)
                if subsection:
                    used_section_ids.add(subsection.section_id)

        # 2. Fetch all chapters/sections and build candidates grouped by section
        chapters = self.db.query(Chapter).filter_by(course_id=course_id).order_by(Chapter.order).all()
        
        # Group candidates by section_id for rotation
        section_candidates = {}  # section_id -> list of chunks
        
        for chapter in chapters:
            for section in chapter.sections:
                for subsection in section.subsections:
                    if filter_keywords:
                        full_context = f"{chapter.title} {section.title} {subsection.title}".lower()
                        sample_chunk = self.db.query(Chunk).filter_by(subsection_id=subsection.id).first()
                        if sample_chunk:
                            full_context += " " + sample_chunk.content[:1000].lower()
                        if not any(k.lower() in full_context for k in filter_keywords):
                            continue
                    
                    available_chunks = self.db.query(Chunk).filter(
                        Chunk.subsection_id == subsection.id,
                        Chunk.chunk_type == ChunkType.MEDIUM,
                        ~Chunk.id.in_(used_chunk_ids)
                    ).all()
                    
                    for chunk in available_chunks:
                        sid = section.id
                        if sid not in section_candidates:
                            section_candidates[sid] = []
                        section_candidates[sid].append(chunk)

        if not section_candidates:
            return None, None

        # 3. Per-student random seed
        seed_str = enrollment_id or "professor_simulation"
        
        # 4. PRIORITIZE sections
        unused_sections = {sid: chunks for sid, chunks in section_candidates.items() if sid not in used_section_ids}
        
        if seed_str == "professor_simulation":
            # True randomness for simulation to avoid "perfect chunk" repetition
            import time
            seed = int(time.time() * 1000)
        else:
            seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        
        rng = random.Random(seed + len(used_chunk_ids))
        


        # Determine if we MUST stay in the same section (Topic Rotation rule)
        if preferred_section_id:
            # Try to pick an UNUSED chunk in this section first
            if preferred_section_id in section_candidates:
                chunks = section_candidates[preferred_section_id]
                rng.shuffle(chunks)
                chosen_chunk = chunks[0]
            else:
                # No UNUSED chunks left in this section, but we MUST stay on topic for 3 turns.
                # Re-fetch a used chunk from this section to satisfy turn continuity.
                fallback_chunks = self.db.query(Chunk).join(Subsection).filter(
                    Subsection.section_id == preferred_section_id,
                    Chunk.chunk_type == ChunkType.MEDIUM
                ).all()
                if fallback_chunks:
                    rng.shuffle(fallback_chunks)
                    chosen_chunk = fallback_chunks[0]
                else:
                    # Truly no chunks in this section? Move on.
                    preferred_section_id = None 

        if not preferred_section_id:
            if unused_sections:
                # Pick from an unused section first
                section_ids = list(unused_sections.keys())
                rng.shuffle(section_ids)
                chosen_section = section_ids[0]
                chunks = unused_sections[chosen_section]
                rng.shuffle(chunks)
                chosen_chunk = chunks[0]
            else:
                # All sections used — pick from any available chunk (unused first)
                all_candidates = []
                for chunks in section_candidates.values():
                    all_candidates.extend(chunks)
                
                if all_candidates:
                    rng.shuffle(all_candidates)
                    chosen_chunk = all_candidates[0]
                else:
                    # Everything in the course used? Pick anything.
                    final_fallback = self.db.query(Chunk).filter_by(chunk_type=ChunkType.MEDIUM).limit(50).all()
                    if not final_fallback: return None, None
                    rng.shuffle(final_fallback)
                    chosen_chunk = final_fallback[0]

        author = self.get_chunk_author(chosen_chunk)
        return chosen_chunk, author

    def get_chunk_author(self, chunk):
        """Identify the author from chunk content or section title."""
        if not chunk:
            return "the author"
        
        # Check chunk content AND section/subsection titles for author names
        search_text = chunk.content[:1000].lower()
        if chunk.subsection:
            search_text += " " + (chunk.subsection.title or "").lower()
            if chunk.subsection.section:
                search_text += " " + (chunk.subsection.section.title or "").lower()
        
        author_map = {
            "anjaria": "Anjaria", "shapiro": "Shapiro",
            "chatterjee": "Chatterjee", "held": "Held", 
            "scott": "Scott", "gupta": "Gupta",
            "ferguson": "Ferguson", "palshikar": "Palshikar", 
            "jeffrey": "Jeffrey", "mehta": "Mehta",
            "khosla": "Khosla", "vaishnav": "Vaishnav"
        }
        
        for key, display in author_map.items():
            if key in search_text:
                return display
        return "the author"

    def _needs_more_exploration(self, subsection_id: int) -> bool:
        """Determines if a subsection needs more coverage."""
        from ..database.models.question import Question
        q_count = self.db.query(Question).filter_by(subsection_id=subsection_id).count()
        return q_count < 20
