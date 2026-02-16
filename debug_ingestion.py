import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from backend.database.session import SessionLocal
from backend.ingestion.processor import MaterialProcessor

def test_ingestion():
    db = SessionLocal()
    try:
        # Create a dummy PDF file for testing if it doesn't exist
        test_file = "test_ingestion.pdf"
        if not os.path.exists(test_file):
            import fitz
            doc = fitz.open()
            # Page 1: Normal text
            page = doc.new_page()
            page.insert_text((50, 50), "This is a test document for ingestion debugging.\n" * 20)
            
            # Page 2: Empty page
            doc.new_page()
            
            # Page 3: Short lines/headers
            page3 = doc.new_page()
            page3.insert_text((50, 50), "Header\n")
            page3.insert_text((50, 70), "Sub\n")
            
            # Page 4: Lowercase start (testing merge logic)
            page4 = doc.new_page()
            page4.insert_text((50, 50), "continuation of previous thought.\n")
            
            doc.save(test_file)
            doc.close()
            print(f"Created test file: {test_file}")

        print("Starting ingestion test...")
        
        processor = MaterialProcessor(db)
        # Assuming course_id 1 exists (default course)
        processor.process_material(course_id=1, file_path=test_file, file_type="pdf")
        
        # Verify embeddings are not all zeros
        from backend.database.models.chunk import Chunk, ChunkType
        chunks = db.query(Chunk).filter(Chunk.chunk_type.in_([ChunkType.SMALL, ChunkType.MEDIUM])).all()
        
        print(f"\n[DEBUG] Total Chunks: {len(chunks)}")
        for c in chunks:
            print(f"  - [{c.chunk_type.value}] {c.content[:50]}...")
            
        # Test semantic merge logic specifically
        print("\n[DEBUG] Testing Semantic Merge Logic...")
        from backend.ingestion.chunking import Chunker
        chunker = Chunker(db)
        test_paragraphs = [
            "Para 1 ends here.",
            "and this should merge.",
            "Para 3 is standalone.",
            "Para 4 is short.",
            "So is Para 5."
        ]
        merged = chunker._semantic_merge(test_paragraphs)
        print(f"Original: {len(test_paragraphs)}")
        print(f"Merged  : {len(merged)}")
        for m in merged:
            print(f"  > {m}")


        print("Ingestion test completed.")
        
    except KeyboardInterrupt:
        print("\n[!] Script interrupted by user.")
    except Exception as e:
        print(f"Ingestion test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_ingestion()
