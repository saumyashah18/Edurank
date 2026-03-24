from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database.models.hierarchy import Chapter, Section, Subsection
from ..database.models.transcript import Transcript

class TopicPlanner:
    def __init__(self, db: Session):
        self.db = db

    def select_next_topic(
        self,
        course_id: int,
        enrollment_id: Optional[str] = None,
        quiz_id: Optional[int] = None,
        filter_keywords: Optional[list] = None,
        used_chunk_ids: Optional[list] = None,
        preferred_section_id: Optional[int] = None
    ) -> tuple:
        """
        New implementation: Concept Graph Traversal.
        Prioritizes Prerequisites and Struggling concepts.
        """
        from ..database.models.student_concept_state import StudentConceptState
        from ..database.models.concept import Concept, ConceptRelation, ConceptChunk
        from ..database.models.chunk import Chunk, ChunkType

        # Step 1: Query student state for this quiz
        states_exist = self.db.query(StudentConceptState).filter_by(
            student_id=enrollment_id, quiz_id=quiz_id
        ).first()

        if not states_exist:
            # Fallback to rotation for first question
            return self._select_by_rotation(course_id, enrollment_id, quiz_id, filter_keywords, used_chunk_ids, preferred_section_id)

        # Step 2: Priority Ordering
        target_concept = None

        # Priority 1: Prerequisites of struggling concepts
        struggling_states = self.db.query(StudentConceptState).filter_by(
            student_id=enrollment_id, quiz_id=quiz_id, status="struggling"
        ).all()

        for s_state in struggling_states:
            # Find prerequisites for this struggling concept
            prereqs = self.db.query(ConceptRelation).filter_by(
                to_concept_id=s_state.concept_id, 
                relation_type="prerequisite"
            ).all()
            for p in prereqs:
                p_state = self.db.query(StudentConceptState).filter_by(
                    student_id=enrollment_id, quiz_id=quiz_id, concept_id=p.from_concept_id
                ).first()
                if not p_state or p_state.status != "demonstrated":
                    target_concept = self.db.query(Concept).get(p.from_concept_id)
                    break
            if target_concept: break

        # Priority 2: Retry struggling directly
        if not target_concept and struggling_states:
            target_concept = self.db.query(Concept).get(struggling_states[0].concept_id)

        # Priority 3: Partial concepts
        if not target_concept:
            partial_state = self.db.query(StudentConceptState).filter_by(
                student_id=enrollment_id, quiz_id=quiz_id, status="partial"
            ).first()
            if partial_state:
                target_concept = self.db.query(Concept).get(partial_state.concept_id)

        # Priority 4: Not tested where prereqs are met
        if not target_concept:
            all_concepts = self.db.query(Concept).filter_by(course_id=course_id).all()
            for c in all_concepts:
                c_state = self.db.query(StudentConceptState).filter_by(
                    student_id=enrollment_id, quiz_id=quiz_id, concept_id=c.id
                ).first()
                if not c_state or c_state.status == "not_tested":
                    # Check prerequisites
                    prereqs = self.db.query(ConceptRelation).filter_by(to_concept_id=c.id, relation_type="prerequisite").all()
                    all_met = True
                    for p in prereqs:
                        p_state = self.db.query(StudentConceptState).filter_by(
                            student_id=enrollment_id, quiz_id=quiz_id, concept_id=p.from_concept_id
                        ).first()
                        if not p_state or p_state.status != "demonstrated":
                            all_met = False
                            break
                    if all_met:
                        target_concept = c
                        break

        # Priority 5: Demonstrated (deepen)
        if not target_concept:
            dem_state = self.db.query(StudentConceptState).filter_by(
                student_id=enrollment_id, quiz_id=quiz_id, status="demonstrated"
            ).order_by(func.random()).first()
            if dem_state:
                target_concept = self.db.query(Concept).get(dem_state.concept_id)

        # Step 3: Find Source Chunk for Target Concept
        if target_concept:
            search_query = self.db.query(Chunk).join(ConceptChunk).filter(
                ConceptChunk.concept_id == target_concept.id,
                Chunk.chunk_type == ChunkType.MEDIUM
            )
            if used_chunk_ids:
                search_query = search_query.filter(~Chunk.id.in_(used_chunk_ids))
            
            chosen_chunk = search_query.first()
            if chosen_chunk:
                return chosen_chunk, self.get_chunk_author(chosen_chunk)

        # Final Fallback
        return self._select_by_rotation(course_id, enrollment_id, quiz_id, filter_keywords, used_chunk_ids, preferred_section_id)

    def _select_by_rotation(self, course_id, enrollment_id, quiz_id, filter_keywords, used_chunk_ids, preferred_section_id):
        """Original rotation logic moved here for fallback."""
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
                subsection = self.db.query(Subsection).get(subsection_id)
                if subsection:
                    used_section_ids.add(subsection.section_id)

        # 2. Fetch all chapters/sections and build candidates
        chapters = self.db.query(Chapter).filter_by(course_id=course_id).order_by(Chapter.order).all()
        section_candidates = {}
        for chapter in chapters:
            for section in chapter.sections:
                for subsection in section.subsections:
                    available_chunks = self.db.query(Chunk).filter(
                        Chunk.subsection_id == subsection.id,
                        Chunk.chunk_type == ChunkType.MEDIUM,
                        ~Chunk.id.in_(used_chunk_ids)
                    ).all()
                    for chunk in available_chunks:
                        sid = section.id
                        if sid not in section_candidates: section_candidates[sid] = []
                        section_candidates[sid].append(chunk)

        if not section_candidates:
            fallback = self.db.query(Chunk).join(Subsection).join(Section).join(Chapter).filter(
                Chapter.course_id == course_id, Chunk.chunk_type == ChunkType.MEDIUM
            ).all()
            if not fallback: return None, None
            c = random.choice(fallback)
            return c, self.get_chunk_author(c)

        seed_str = enrollment_id or "professor_simulation"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed + len(used_chunk_ids))

        unused_sections = {sid: chunks for sid, chunks in section_candidates.items() if sid not in used_section_ids}
        if unused_sections:
            sid = rng.choice(list(unused_sections.keys()))
            chosen_chunk = rng.choice(unused_sections[sid])
        else:
            all_c = []
            for chunks in section_candidates.values(): all_c.extend(chunks)
            chosen_chunk = rng.choice(all_c) if all_c else None

        if not chosen_chunk: return None, None
        return chosen_chunk, self.get_chunk_author(chosen_chunk)

    def get_current_bloom_phase(self, student_id: str, quiz_id: int, concept_id: int) -> int:
        """Returns current Bloom's phase (1-5) for this student/concept/quiz."""
        from ..database.models.student_concept_state import StudentConceptState
        state = self.db.query(StudentConceptState).filter_by(
            student_id=student_id, quiz_id=quiz_id, concept_id=concept_id
        ).first()
        if not state:
            return 1
        # Advance phase based on confidence:
        # confidence >= 0.8 at phase N → move to phase N+1 (max 5)
        if state.confidence >= 0.8 and state.status == "demonstrated":
            return min(5, state.attempts // 2 + 1)
        return max(1, state.attempts // 3 + 1)

    def get_struggling_concepts(self, student_id: str, quiz_id: int) -> list:
        """Returns list of Concept objects where student status is struggling."""
        from ..database.models.student_concept_state import StudentConceptState
        from ..database.models.concept import Concept
        states = self.db.query(StudentConceptState).filter_by(
            student_id=student_id, quiz_id=quiz_id, status="struggling"
        ).all()
        concepts = []
        for state in states:
            concept = self.db.query(Concept).get(state.concept_id)
            if concept:
                concepts.append(concept)
        return concepts


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
