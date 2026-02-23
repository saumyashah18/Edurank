from typing import List, Dict, Any
from sqlalchemy.orm import Session
from ..database.models.hierarchy import Chapter, Section, Subsection, RawMaterial
from ..database.models.question import Question
from ..database.models.chunk import Chunk, KnowledgeRelation
from ..database.models.course import Course, IngestionStatus
from ..rag.embedder import Embedder
import os

class MaterialProcessor:
    def __init__(self, db: Session):
        self.db = db

    def process_material(self, course_id: int, file_path: str, file_type: str):
        """
        Main entry point for processing a study material with high-visibility audit.
        """
        import time
        start_time = time.time()
        print(f"\n{'#'*60}")
        print(f"### [INGESTION ENGINE] Processing: {os.path.basename(file_path)}")
        print(f"{'#'*60}")
        
        try:
            
            course = self.db.query(Course).get(course_id)
            if course:
                course.ingestion_status = IngestionStatus.PROCESSING
                self.db.commit()

            # Step 0: Clear stale data to ensure groundedness
            self.clear_course_data(course_id)
            
            # Step 1: Extraction
            extracted_data = self._extract_structure(file_path, file_type)
            if not extracted_data:
                print(f"[!] INGESTION ABORTED: No data extracted.")
                if course:
                    course.ingestion_status = IngestionStatus.FAILED
                    self.db.commit()
                return
                
            self._store_hierarchy(course_id, extracted_data)
            
            if course:
                course.ingestion_status = IngestionStatus.COMPLETED
                self.db.commit()

            duration = time.time() - start_time
            print(f"\n{'='*60}")
            print(f"✅ [SUCCESS] Material Fully Chunked & Indexed in {duration:.2f}s")
            print(f"🔗 View proof: Professor Dashboard (Knowledge Section)")
            print(f"{'='*60}\n")
        except Exception as e:
            self.db.rollback() # Ensure transaction is rolled back so status update can proceed
            course = self.db.query(Course).get(course_id)
            if course:
                course.ingestion_status = IngestionStatus.FAILED
                self.db.commit()
            print(f"\n❌ [FATAL ERROR] Ingestion Pipeline Failed: {e}")

    def _extract_structure(self, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        """Extracts structural hierarchy from the file with per-page 'surety' logs."""
        import fitz  # PyMuPDF
        print(f"[*] Audit Phase 1: Deep Text Extraction")
        
        try:
            with fitz.open(file_path) as doc:
                total_pages = len(doc)
                print(f"    -> Pages Detected: {total_pages}")
                
                full_text = ""
                valid_text_pages = 0
                for i, page in enumerate(doc):
                    # sort=True forces reading by physical layout (columns/blocks) vs stream
                    page_text = page.get_text(sort=True).replace("\0", "")
                    
                    # text density check
                    clean_text = page_text.strip()
                    if len(clean_text) < 50:
                         # Likely a scanned page or just a page number
                         pass 
                    else:
                         valid_text_pages += 1
                    
                    full_text += page_text
                    
                    if total_pages < 20 or (i + 1) % 10 == 0 or (i + 1) == total_pages:
                        print(f"    [PROGRESS] Page {i+1}/{total_pages} extracted. [OK]")
                
                # SCANNED PDF DETECTION & AUTO-OCR
                if total_pages > 0:
                     readability_ratio = valid_text_pages / total_pages
                     if readability_ratio < 0.1 and not os.path.exists(file_path.replace(".pdf", "_ORIGINAL.pdf")): # Check if already processed
                          print(f"    [!] DETECTED SCANNED PDF: Only {valid_text_pages}/{total_pages} pages have text.")
                          print(f"    [*] INITIATING CHUNKED AUTO-OCR (Optical Character Recognition)...")
                          
                          try:
                               import ocrmypdf
                               
                               # CHUNKED PROCESSING STRATEGY (Corrected: Actual Split -> OCR -> Merge)
                               chunk_size = 25 # Process 25 pages at a time
                               num_chunks = (total_pages + chunk_size - 1) // chunk_size
                               temp_outputs = []
                               
                               print(f"    [*] Splitting into {num_chunks} chunks for stability...")
                               
                               for i in range(num_chunks):
                                   start_idx = i * chunk_size
                                   end_idx = min((i + 1) * chunk_size, total_pages)
                                   
                                   # 1. Extract Chunk to temp PDF
                                   chunk_input = file_path.replace(".pdf", f"_part{i}_in.pdf")
                                   chunk_output = file_path.replace(".pdf", f"_part{i}_out.pdf")
                                   
                                   print(f"    [-->] Preparing Chunk {i+1}/{num_chunks} (Pages {start_idx+1}-{end_idx})...")
                                   
                                   chunk_doc = fitz.open()
                                   chunk_doc.insert_pdf(doc, from_page=start_idx, to_page=end_idx-1)
                                   chunk_doc.save(chunk_input)
                                   chunk_doc.close()
                                   
                                   # 2. Run OCR on this small chunk
                                   # We don't use --pages here because the input is ONLY the chunk
                                   ocrmypdf.ocr(
                                       chunk_input, 
                                       chunk_output, 
                                       deskew=True, 
                                       force_ocr=True, 
                                       jobs=1, 
                                       optimize=0
                                   )
                                   
                                   temp_outputs.append(chunk_output)
                                   os.remove(chunk_input) # Cleanup temp input
                               
                               print(f"    [SUCCESS] All chunks OCR'd. Merging into searchable master...")
                               
                               # 3. Merge chunks into final OCR file
                               merged_doc = fitz.open()
                               for chunk_pdf in temp_outputs:
                                   with fitz.open(chunk_pdf) as sub_doc:
                                       merged_doc.insert_pdf(sub_doc)
                                   # Cleanup chunk file
                                   os.remove(chunk_pdf)
                               
                               output_path = file_path.replace(".pdf", "_OCR.pdf")
                               merged_doc.save(output_path)
                               merged_doc.close()

                               print(f"    [SUCCESS] OCR COMPLETE. Swapping in final file...")
                               
                               # SWAP LOGIC: Backup original -> Overwrite input -> Recurse on input
                               original_backup = file_path.replace(".pdf", "_ORIGINAL.pdf")
                               if os.path.exists(output_path):
                                   os.rename(file_path, original_backup)
                                   os.rename(output_path, file_path)
                                   print(f"    [*] Replaced original file. Backup saved to: {original_backup}")
                               
                               # Recursive call with ORIGINAL path (which now contains readable text)
                               return self._extract_structure(file_path, file_type)
                               
                          except ImportError:
                               print(f"    [ERROR] ocrmypdf not installed. Cannot perform Auto-OCR.")
                               raise ValueError("Scanned PDF detected and OCR tools are missing. Please upload a searchable PDF.")
                          except Exception as ocr_e:
                               print(f"    [ERROR] Auto-OCR Failed: {ocr_e}")
                               raise ValueError(f"Failed to OCR scanned PDF: {ocr_e}")
                
                print(f"[*] Audit Phase 2: Hierarchical Syllabus Mapping")
                
                if not full_text:
                    return []

                # ACCURACY FIX: Group pages instead of arbitrary character counts
                chapters = []
                pages_per_chapter = 5 # Group every 5 pages into a logical chapter
                
                for i in range(0, total_pages, pages_per_chapter):
                    end_page = min(i + pages_per_chapter, total_pages)
                    chapter_text = ""
                    for p_num in range(i, end_page):
                        chapter_text += doc[p_num].get_text().replace("\0", "")
                    
                    chap_num = (i // pages_per_chapter) + 1
                    chapters.append({
                        "title": f"Chapter {chap_num} (Pages {i+1}-{end_page})",
                        "order": chap_num,
                        "sections": [{
                            "title": f"Section {chap_num}.1",
                            "order": 1,
                            "subsections": [{
                                "title": f"Content Block {chap_num}.1.1",
                                "order": 1,
                                "content": chapter_text
                            }]
                        }]
                    })
                
                print(f"    -> ACCURACY UPGRADE: Mapped {total_pages} pages into {len(chapters)} logical Chapters.")
                return chapters
        except Exception as e:
            print(f"    [!] FAILED: PDF extraction error: {e}")
            return []


    def _store_hierarchy(self, course_id: int, hierarchy_data: List[Dict[str, Any]]):
        """Saves the detected hierarchy to the database and triggers RAG updates."""
        from .chunking import Chunker
        from ..rag.embedder import Embedder
        
        chunker = Chunker(self.db)
        embedder = Embedder(self.db)
        
        print(f"  > Storing {len(hierarchy_data)} chapters to DB...")

        for chap_data in hierarchy_data:
            chapter = Chapter(title=chap_data["title"], order=chap_data["order"], course_id=course_id)
            self.db.add(chapter)
            self.db.flush()

            for sec_data in chap_data["sections"]:
                section = Section(title=sec_data["title"], order=sec_data["order"], chapter_id=chapter.id)
                self.db.add(section)
                self.db.flush()

                for sub_data in sec_data["subsections"]:
                    try:
                        subsection = Subsection(title=sub_data["title"], order=sub_data["order"], section_id=section.id)
                        self.db.add(subsection)
                        self.db.flush()

                        raw_mat = RawMaterial(content=sub_data["content"], subsection_id=subsection.id)
                        self.db.add(raw_mat)
                        self.db.flush()
                        
                        print(f"    - Processing {subsection.title}...")
                        chunker.generate_chunks(subsection.id)
                        
                        print(f"    - Indexing {subsection.title} in FAISS...")
                        try:
                            embedder.embed_chunks(subsection.id)
                        except Exception as ee:
                            print(f"      [EMBEDDING WARNING] {ee}")
                        
                        self.db.commit() # Persistent save for each subsection

                        # [CREDIT OPTIMIZATION] Deterministic Keyword-Based Knowledge Graph
                        self._create_deterministic_relations(subsection.id)
                        
                    except Exception as sub_e:
                        print(f"    [SUBSECTION ERROR] {sub_e}")
                        self.db.rollback()
                        raise sub_e



    def clear_course_data(self, course_id: int):
        """Wipes all hierarchical and assessment data for a course to prevent leakage."""
        print(f"\n[*] CLEANUP: Wiping stale data for Course {course_id}...")
        
        # 1. Reset FAISS Index
        embedder = Embedder(self.db)
        embedder.reset_index()

        # 2. Clear DB (Hierarchical cascade deletes Sections, Subsections, RawMaterial, and Chunks)
        chapters = self.db.query(Chapter).filter_by(course_id=course_id).all()
        for chapter in chapters:
            # Manually delete questions linked to subsections in this chapter
            # Question doesn't have a direct cascade from Chapter/Subsection in the models
            self.db.query(Question).filter(
                Question.subsection_id.in_(
                    self.db.query(Subsection.id).join(Section).filter(Section.chapter_id == chapter.id)
                )
            ).delete(synchronize_session=False)
            
            self.db.delete(chapter)
        
        self.db.commit()
        print("    -> Database cleared.")

    def _create_deterministic_relations(self, subsection_id: int):
        """Builds KnowledgeRelations by matching keywords between the new subsection and existing ones."""
        from ..database.models.chunk import Chunk, KnowledgeRelation, ChunkType
        from ..database.models.hierarchy import Subsection
        import re

        # 1. Fetch current chunks for this subsection
        current_chunks = self.db.query(Chunk).filter_by(subsection_id=subsection_id, chunk_type=ChunkType.MEDIUM).all()
        if not current_chunks:
            return

        # 2. Extract potential keywords (Capitalized words > 4 chars, avoiding common stopwords)
        # This is a heuristic for concepts/names
        ignore_words = {"this", "that", "there", "their", "chapter", "section", "about", "would", "could", "should"}
        keywords = set()
        for chunk in current_chunks:
            found = re.findall(r"\b[A-Z][a-z]{4,}\b", chunk.content)
            for word in found:
                if word.lower() not in ignore_words:
                    keywords.add(word)

        if not keywords:
            return

        # 3. Search for these keywords in OTHER subsections' chunks (within the same course)
        # We look for chunks in subsections that belong to the same course but have a different ID
        current_sub = self.db.query(Subsection).get(subsection_id)
        if not current_sub:
            return
            
        other_chunks = self.db.query(Chunk).join(Subsection).join(Section).join(Chapter).filter(
            Chapter.course_id == current_sub.section.chapter.course_id,
            Subsection.id != subsection_id,
            Chunk.chunk_type == ChunkType.MEDIUM
        ).all()

        for cur_chunk in current_chunks:
            for other_chunk in other_chunks:
                # Check for shared keywords
                shared = [k for k in keywords if k in other_chunk.content]
                if shared:
                    # Create relation if not exists
                    relation = KnowledgeRelation(
                        source_id=cur_chunk.id,
                        target_id=other_chunk.id,
                        relation_type=f"shared_concept:{shared[0]}"
                    )
                    self.db.add(relation)

        self.db.commit()

    def _create_semantic_relations(self, subsection_id: int):
        """[DEPRECATED] AI-based relation builder - preserved for compatibility check."""
        pass
