import json
import re
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database.models.chunk import Chunk, ChunkType
from ..database.models.concept import Concept, ConceptRelation, ConceptChunk
from ..quiz.llm_service import llm
from ..utils.llm_logger import LLMCallLogger

class ConceptExtractor:
    def __init__(self, db: Session):
        self.db = db
        self.llm = llm

    def _extract_from_batch(self, chunks: List[Chunk], course_id: int) -> None:
        """
        Sends up to 5 chunks in a single LLM call.
        Extracts concepts independently per chunk.
        Falls back to individual calls if batch JSON fails.
        """
        system_prompt = (
            "You are an academic knowledge graph builder. "
            "Extract key concepts from each text chunk independently. "
            "Respond ONLY with valid JSON. No preamble, no markdown, "
            "no code fences. Never create relations between concepts "
            "from different chunks."
        )

        chunk_blocks = ""
        for i, chunk in enumerate(chunks, 1):
            chunk_blocks += f"\nCHUNK {i}:\n{chunk.content}\n"

        user_prompt = f"""Extract academic concepts from each chunk below.
Process each chunk INDEPENDENTLY. Do NOT link concepts across chunks.

{chunk_blocks}

For each chunk return:
- name: short noun phrase (2-5 words)
- description: one sentence
- difficulty_level: "foundational", "intermediate", or "advanced"
- relations: relationships to OTHER concepts in THE SAME CHUNK ONLY
  Each relation: {{"to_concept_name": "...", 
  "relation_type": "prerequisite|part_of|contrasts_with|leads_to"}}

Respond with EXACTLY:
{{
  "batch": [
    {{
      "chunk_index": 1,
      "concepts": [
        {{
          "name": "...",
          "description": "...",
          "difficulty_level": "...",
          "relations": [
            {{"to_concept_name": "...", "relation_type": "..."}}
          ]
        }}
      ]
    }}
  ]
}}"""

        try:
            from ..utils.llm_logger import LLMCallLogger
            raw = LLMCallLogger.timed_call(
                caller="ConceptExtractor.batch",
                prompt=user_prompt,
                llm_fn=lambda: self.llm.generate_content(
                    user_prompt, system_prompt=system_prompt
                ),
                extra={"batch_size": len(chunks), "course_id": course_id}
            )
        except ImportError:
            raw = self.llm.generate_content(
                user_prompt, system_prompt=system_prompt
            )

        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            if lines[0].startswith("```"): lines = lines[1:]
            if lines[-1].strip() == "```": lines = lines[:-1]
            clean = "\n".join(lines).strip()

        try:
            data = json.loads(clean)
            batch_results = data.get("batch", [])
            for result in batch_results:
                idx = result.get("chunk_index", 1) - 1
                if 0 <= idx < len(chunks):
                    chunk = chunks[idx]
                    concepts_data = result.get("concepts", [])
                    self._upsert_concepts(concepts_data, chunk, course_id)
            return
        except json.JSONDecodeError:
            print(f"[ConceptExtractor] Batch parse failed for "
                  f"{len(chunks)} chunks, falling back to individual calls")
            for chunk in chunks:
                self._extract_from_chunk_single(chunk, course_id)

    def _extract_from_chunk_single(self, chunk: Chunk, course_id: int) -> None:
        """
        Fallback: processes one chunk at a time.
        Used when batch JSON parsing fails.
        Identical logic to original _extract_from_chunk but stores
        via _upsert_concepts() instead of returning a list.
        """
        system_prompt = (
            "You are an academic knowledge graph builder. Extract key concepts from the provided text. "
            "Respond ONLY with valid JSON. No preamble, no markdown, no code fences."
        )

        user_prompt = f"""Extract all key academic concepts from this text. For each concept identify:
   - name: short noun phrase (2-5 words max)
   - description: one sentence explaining it
   - difficulty_level: one of "foundational", "intermediate", "advanced"
   - relations: list of relationships to OTHER concepts in this text only
     Each relation: {{"to_concept_name": "...", "relation_type": "prerequisite|part_of|contrasts_with|leads_to"}}

   TEXT:
   {chunk.content}

   Respond with this exact JSON structure:
   {{
     "concepts": [
       {{
         "name": "...",
         "description": "...",
         "difficulty_level": "...",
         "relations": [
           {{"to_concept_name": "...", "relation_type": "..."}}
         ]
       }}
     ]
   }}"""

        try:
            from ..utils.llm_logger import LLMCallLogger
            raw = LLMCallLogger.timed_call(
                caller="ConceptExtractor",
                prompt=user_prompt,
                llm_fn=lambda: self.llm.generate_content(user_prompt, system_prompt=system_prompt),
                extra={"chunk_id": chunk.id, "course_id": course_id}
            )
        except ImportError:
            raw = self.llm.generate_content(user_prompt, system_prompt=system_prompt)

        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            clean = "\n".join(lines).strip()

        try:
            data = json.loads(clean)
            concepts = data.get("concepts", [])
            valid_concepts = [c for c in concepts if "name" in c and c["name"]]
            self._upsert_concepts(valid_concepts, chunk, course_id)
        except Exception as e:
            print(f"[ConceptExtractor] JSON parse error: {e}")

    def _upsert_concepts(
        self,
        concepts_data: List[dict],
        chunk: Chunk,
        course_id: int
    ) -> List[Concept]:
        """
        Upserts a list of concept dicts into the DB for a given chunk.
        Returns list of upserted Concept objects.
        """
        from sqlalchemy import func
        from sqlalchemy.exc import IntegrityError
        from ..database.models.concept import Concept, ConceptChunk

        upserted = []
        for concept_dict in concepts_data:
            name = concept_dict.get("name", "")
            if isinstance(name, str):
                name = name.strip()
            if not name:
                continue
            try:
                existing = self.db.query(Concept).filter(
                    Concept.course_id == course_id,
                    func.lower(Concept.name) == name.lower()
                ).first()

                if existing:
                    if concept_dict.get("description"):
                        existing.description = concept_dict["description"]
                    if concept_dict.get("difficulty_level"):
                        existing.difficulty_level = concept_dict["difficulty_level"]
                    concept = existing
                else:
                    concept = Concept(
                        course_id=course_id,
                        name=name,
                        description=concept_dict.get("description"),
                        difficulty_level=concept_dict.get("difficulty_level")
                    )
                    self.db.add(concept)
                    self.db.flush()

                # Link concept to source chunk
                existing_link = self.db.query(ConceptChunk).filter_by(
                    concept_id=concept.id,
                    chunk_id=chunk.id
                ).first()
                if not existing_link:
                    self.db.add(ConceptChunk(
                        concept_id=concept.id,
                        chunk_id=chunk.id
                    ))

                # Store raw relations for _store_relations()
                concept._raw_relations = concept_dict.get("relations", [])
                upserted.append(concept)

            except IntegrityError:
                self.db.rollback()
                print(f"[ConceptExtractor] Skipping duplicate: {name}")
                continue

        return upserted

    def extract_and_store(self, subsection_id: int, course_id: int) -> List[Concept]:
        """
        Fetches MEDIUM chunks for this subsection.
        Processes them in batches of 5.
        Upserts all concepts and relations.
        Returns all upserted Concept objects.
        """
        BATCH_SIZE = 5

        chunks = self.db.query(Chunk).filter_by(
            subsection_id=subsection_id,
            chunk_type=ChunkType.MEDIUM
        ).all()

        if not chunks:
            print(f"[ConceptExtractor] No MEDIUM chunks for "
                  f"subsection {subsection_id}")
            return []

        all_concepts = []

        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            print(f"[ConceptExtractor] Batch {i//BATCH_SIZE + 1}/"
                  f"{(len(chunks) + BATCH_SIZE - 1)//BATCH_SIZE} "
                  f"({len(batch)} chunks)")
            self._extract_from_batch(batch, course_id)

        # Collect all concepts upserted for this subsection
        from ..database.models.concept import ConceptChunk, Concept
        chunk_ids = [c.id for c in chunks]
        concept_ids = [
            cc.concept_id for cc in
            self.db.query(ConceptChunk)
            .filter(ConceptChunk.chunk_id.in_(chunk_ids)).all()
        ]
        all_concepts = self.db.query(Concept).filter(
            Concept.id.in_(concept_ids)
        ).all()

        # Store relations after all concepts are in DB
        self._store_relations(all_concepts, course_id)

        self.db.commit()
        return all_concepts

    def _store_relations(self, concepts: List[Concept], course_id: int):
        """
        For each concept, look at its raw extracted relations dict and create ConceptRelation rows.
        Only create a relation if BOTH the from_concept and to_concept exist in the DB for this course.
        """
        allowed_types = {"prerequisite", "part_of", "contrasts_with", "leads_to"}

        for from_concept in concepts:
            raw_rels = getattr(from_concept, "_raw_relations", [])
            for rel_data in raw_rels:
                to_name = rel_data.get("to_concept_name", "").strip()
                rel_type = rel_data.get("relation_type", "").lower().strip()

                if not to_name or rel_type not in allowed_types:
                    continue

                # Look up to_concept in DB for this course (case-insensitive)
                to_concept = self.db.query(Concept).filter(
                    Concept.course_id == course_id,
                    func.lower(Concept.name) == to_name.lower()
                ).first()

                if to_concept and from_concept.id != to_concept.id:
                    try:
                        # Check for existing relation to avoid IntegrityError
                        existing = self.db.query(ConceptRelation).filter_by(
                            from_concept_id=from_concept.id,
                            to_concept_id=to_concept.id,
                            relation_type=rel_type
                        ).first()
                        
                        if not existing:
                            new_rel = ConceptRelation(
                                from_concept_id=from_concept.id,
                                to_concept_id=to_concept.id,
                                relation_type=rel_type
                            )
                            self.db.add(new_rel)
                    except Exception as e:
                        print(f"[ConceptExtractor] Relation error: {e}")
                        continue
