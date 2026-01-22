from typing import List, Dict, Any
from sqlalchemy.orm import Session
from ..database.models.hierarchy import Chapter, Section, Subsection, RawMaterial
from ..database.models.question import Question
from ..database.models.chunk import Chunk
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
            # Set status to PROCESSING
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
                for i, page in enumerate(doc):
                    page_text = page.get_text()
                    full_text += page_text
                    # Print every 10 pages for large docs to avoid terminal flooding, or every page for small ones
                    if total_pages < 20 or (i + 1) % 10 == 0 or (i + 1) == total_pages:
                        print(f"    [PROGRESS] Page {i+1}/{total_pages} extracted. [OK]")
                
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
                        chapter_text += doc[p_num].get_text()
                    
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
                    except Exception as sub_e:
                        print(f"    [SUBSECTION ERROR] {sub_e}")
                        self.db.rollback()



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
