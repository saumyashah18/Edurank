import sys
from backend.database.session import SessionLocal
from backend.database.models.transcript import Transcript

db = SessionLocal()
transcripts = db.query(Transcript).filter(Transcript.quiz_id == 78).all()
print(f"Quiz 78 Transcripts: {len(transcripts)}")
for t in transcripts:
    print(f" - {t.student_name} ({t.enrollment_id}): {t.student_answer}")
