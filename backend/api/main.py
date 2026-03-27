from fastapi import FastAPI, Depends, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
import os
import json

from ..database.session import SessionLocal, init_db
from ..ingestion.processor import MaterialProcessor
from ..ingestion.chunking import Chunker
from ..rag.embedder import Embedder, RAGService
from ..rag.evaluation import EvaluationService
from ..quiz.professor_bot import ProfessorBot
from ..quiz.planner import TopicPlanner
from ..quiz.quiz_manager import QuizManager
from ..database.models.question import Question, QuestionStatus
from ..database.models.hierarchy import Chapter, Section, Subsection, RawMaterial
from ..database.models.transcript import Transcript, Quiz
from ..voice.service import voice_service
from ..quiz.llm_service import llm
import base64


app = FastAPI(title="AIssociate AI System")

# Enable CORS with explicit null support for local files
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "null"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"GLOBAL ERROR: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"}
    )



@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from dotenv import load_dotenv

load_dotenv()

@app.on_event("startup")
def startup_event():
    init_db()
    # Ensure default course exists for simulation
    db = SessionLocal()
    try:
        from ..database.models.course import Course, IngestionStatus
        course = db.query(Course).filter_by(id=1).first()
        if not course:
            print("INFO: Creating default course (ID: 1) for simulation...")
            default_course = Course(id=1, title="General Assessment Course", description="Default course for AI simulation")
            db.add(default_course)
            db.commit()
    except Exception as e:
        print(f"ERROR: Could not create default course: {e}")
    finally:
        db.close()

# --- Auth & User Endpoints ---

@app.post("/auth/register")
def register_professor(data: dict, db: Session = Depends(get_db)):
    """Registers a professor with @ahduni.edu.in restriction."""
    from ..database.models.user import User, UserRole
    email = data.get("email")
    if not email or not email.endswith("@ahduni.edu.in"):
        raise HTTPException(status_code=400, detail="Only @ahduni.edu.in emails allowed")
    
    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            full_name=data.get("full_name"),
            firebase_uid=data.get("firebase_uid"),
            role=UserRole.PROFESSOR
        )
        db.add(user)
        db.commit()
    return {"status": "success", "user_id": user.id}

@app.get("/professor/assessments")
def get_professor_assessments(db: Session = Depends(get_db)):
    """List all assessments for the professor dashboard."""
    quizzes = db.query(Quiz).order_by(Quiz.id.desc()).all() # Filter by professor in future
    return [{
        "id": q.id,
        "title": q.title,
        "course_name": q.course.title if q.course else "Unknown Course",
        "total_questions": q.total_questions,
        "is_finalized": q.is_finalized == 1,
        "password": q.password,
        "transcripts_count": len(q.transcripts)
    } for q in quizzes]


# --- Professor Endpoints ---

def run_document_ingestion(course_id: int, document_id: int, file_path: str):
    """
    Background worker with retry logic and granular status tracking.
    Retries the full ingestion up to MAX_RETRIES times on failure.
    Sets ingestion_error on Document with specific failure reason.
    """
    from ..database.models.course import Document, IngestionStatus

    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 5

    for attempt in range(1, MAX_RETRIES + 1):
        db = SessionLocal()
        try:
            print(f"[Ingestion] Attempt {attempt}/{MAX_RETRIES} for Document {document_id}, file: {file_path}")
            processor = MaterialProcessor(db)
            file_ext = file_path.lower().split(".")[-1] if "." in file_path else "pdf"
            processor.process_material(course_id, document_id, file_path, file_ext)
            print(f"[Ingestion] SUCCESS on attempt {attempt} for Document {document_id}")
            return  # Success — exit retry loop

        except Exception as e:
            db.rollback()
            error_msg = str(e)
            print(f"[Ingestion] FAILED attempt {attempt}/{MAX_RETRIES}: {error_msg}")

            # Update document status with attempt info
            try:
                doc = db.query(Document).get(document_id)
                if doc:
                    if attempt < MAX_RETRIES:
                        doc.ingestion_status = IngestionStatus.EXTRACTING  # Will retry
                        doc.ingestion_error = f"Attempt {attempt} failed: {error_msg}. Retrying..."
                    else:
                        doc.ingestion_status = IngestionStatus.FAILED
                        doc.ingestion_error = f"All {MAX_RETRIES} attempts failed. Last error: {error_msg}"
                    db.commit()
            except Exception as db_e:
                print(f"[Ingestion] Could not update Document status: {db_e}")

            if attempt < MAX_RETRIES:
                import time
                time.sleep(RETRY_DELAY_SECONDS)
        finally:
            db.close()

def run_document_ingestion_locked(course_id: int, document_id: int, file_path: str):
    """Wraps run_document_ingestion with ingestion lock release."""
    try:
        run_document_ingestion(course_id, document_id, file_path)
    finally:
        db = SessionLocal()
        try:
            from ..database.models.course import Document
            doc = db.query(Document).get(document_id)
            if doc:
                doc.is_ingesting = False
                db.commit()
            print(f"[Ingestion] Lock released for Document {document_id}")
        except Exception as e:
            print(f"[Ingestion] Could not release lock for Document {document_id}: {e}")
        finally:
            db.close()

@app.post("/professor/upload/{course_id}")
async def upload_material(
    course_id: int, 
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """Uploads material, saves it as a Document in the library, and triggers background ingestion."""
    from ..database.models.course import Course, Document, IngestionStatus

    course = db.query(Course).get(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    new_doc = Document(
        course_id=course_id,
        filename=file.filename,
        ingestion_status=IngestionStatus.PENDING,
        is_ingesting=True
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    # Save file locally
    file_path = f"uploads/{file.filename}"
    os.makedirs("uploads", exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    print(f"[Upload] Triggering ingestion for Document {new_doc.id}, file: {file.filename}")
    background_tasks.add_task(run_document_ingestion_locked, course_id, new_doc.id, file_path)
    
    return {"status": "File uploaded. Processing in background.", "filename": file.filename, "document_id": new_doc.id}



@app.get("/professor/questions/pending", response_model=List[dict])
def get_pending_questions(db: Session = Depends(get_db)):
    """Fetch questions generated by AI but not yet approved."""
    print("DEBUG: Fetching pending questions...")
    questions = db.query(Question).filter_by(status=QuestionStatus.PENDING).all()
    return [{"id": q.id, "text": q.question_text, "answer": q.ideal_answer} for q in questions]


@app.post("/professor/questions/{question_id}/review")
def review_question(question_id: int, status: str, db: Session = Depends(get_db)):
    """Approve or reject a question."""
    question = db.query(Question).get(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if status == "approve":
        question.status = QuestionStatus.APPROVED
    elif status == "reject":
        question.status = QuestionStatus.REJECTED
    
    db.commit()
    return {"status": "Updated"}

@app.post("/professor/generate/{course_id}")
def trigger_generation(course_id: int, db: Session = Depends(get_db)):
    """Triggers the ProfessorBot to generate questions deterministically across the syllabus."""
    print(f"Triggering deterministic question generation for course {course_id}...")
    planner = TopicPlanner(db)
    rag = RAGService(db, Embedder(db))
    bot = ProfessorBot(db, rag, planner)
    res = bot.generate_questions_for_course(course_id)
    print(f"Generation result: {res}")
    return {"status": "Generation request processed", "details": res}


@app.get("/professor/documents/{course_id}")
def get_course_documents(course_id: int, db: Session = Depends(get_db)):
    """Fetch all documents in the library for a course."""
    from ..database.models.course import Document
    docs = db.query(Document).filter_by(course_id=course_id).order_by(Document.id.desc()).all()
    return [{
        "id": d.id,
        "filename": d.filename,
        "status": d.ingestion_status or "PENDING",
        "error": d.ingestion_error,
        "created_at": d.created_at
    } for d in docs]

@app.get("/professor/document/{doc_id}/status")
def get_document_status(doc_id: int, db: Session = Depends(get_db)):
    """Fetch the progress status of material processing for a specific document."""
    from ..database.models.course import Document
    doc = db.query(Document).get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "status": doc.ingestion_status or "PENDING",
        "error": doc.ingestion_error
    }


@app.delete("/professor/document/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """Deletes a document and all its associated fragments from the database."""
    from ..database.models.course import Document
    from ..database.models.chunk import Chunk, KnowledgeRelation
    from ..database.models.hierarchy import Chapter, Section, Subsection, RawMaterial
    from ..database.models.question import Question
    from ..database.models.concept import ConceptChunk

    doc = db.query(Document).get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        # 0. Collect all chunk IDs for this document (needed for relation cleanup)
        chunk_ids = [c.id for c in db.query(Chunk).filter(Chunk.document_id == doc_id).all()]
        
        if chunk_ids:
            # Clean KnowledgeRelation rows referencing these chunks
            db.query(KnowledgeRelation).filter(
                (KnowledgeRelation.source_id.in_(chunk_ids)) |
                (KnowledgeRelation.target_id.in_(chunk_ids))
            ).delete(synchronize_session=False)
            
            # Clean ConceptChunk links referencing these chunks
            db.query(ConceptChunk).filter(
                ConceptChunk.chunk_id.in_(chunk_ids)
            ).delete(synchronize_session=False)

        # 1. Wipe chunks targeted to this document
        db.query(Chunk).filter(Chunk.document_id == doc_id).delete(synchronize_session=False)
        
        # 2. Cascade through hierarchy: chapters → sections → subsections
        chapters = db.query(Chapter).filter(Chapter.document_id == doc_id).all()
        for chapter in chapters:
            sections = db.query(Section).filter(Section.chapter_id == chapter.id).all()
            for section in sections:
                subsection_ids = [s.id for s in db.query(Subsection).filter(Subsection.section_id == section.id).all()]
                if subsection_ids:
                    # Delete questions, raw materials, and remaining chunks tied to these subsections
                    db.query(Question).filter(Question.subsection_id.in_(subsection_ids)).delete(synchronize_session=False)
                    db.query(RawMaterial).filter(RawMaterial.subsection_id.in_(subsection_ids)).delete(synchronize_session=False)
                    # Clean relations for subsection-linked chunks too
                    sub_chunk_ids = [c.id for c in db.query(Chunk).filter(Chunk.subsection_id.in_(subsection_ids)).all()]
                    if sub_chunk_ids:
                        db.query(KnowledgeRelation).filter(
                            (KnowledgeRelation.source_id.in_(sub_chunk_ids)) |
                            (KnowledgeRelation.target_id.in_(sub_chunk_ids))
                        ).delete(synchronize_session=False)
                        db.query(ConceptChunk).filter(
                            ConceptChunk.chunk_id.in_(sub_chunk_ids)
                        ).delete(synchronize_session=False)
                    db.query(Chunk).filter(Chunk.subsection_id.in_(subsection_ids)).delete(synchronize_session=False)
                    db.query(Subsection).filter(Subsection.id.in_(subsection_ids)).delete(synchronize_session=False)
                db.query(Section).filter(Section.id == section.id).delete(synchronize_session=False)
            db.query(Chapter).filter(Chapter.id == chapter.id).delete(synchronize_session=False)

        db.delete(doc)
        db.commit()
        return {"status": "Document deleted successfully."}
    except Exception as e:
        db.rollback()
        print(f"[API ERROR] Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document from database")

# --- Lazy-Loaded Singletons for Stability ---
class AIServices:
    def __init__(self, db: Session):
        self.embedder = Embedder(db)
        self.rag = RAGService(db, self.embedder)
        self.eval_svc = EvaluationService(db, self.rag)
        self.planner = TopicPlanner(db)
        self.bot = ProfessorBot(db, self.rag, self.planner)

def get_ai_services(db: Session = Depends(get_db)):
    """FastAPI dependency to provide isolated AI services per request."""
    return AIServices(db)

def clean_context_label(text: str) -> str:
    """Removes Section/Chapter numbering from UI labels."""
    import re
    if not text: return "Reading"
    # Removes "Section 80.1", "Chapter 5", etc. case-insensitive
    text = re.sub(r"(?i)(?:section|chapter|ch|unit)\s*\d+(\.\d+)*[:\- ]*", "", text)
    return text.strip() or "Reading"

@app.get("/professor/simulate/next")
def get_next_simulation_question(
    course_id: int, 
    exclude_ids: Optional[str] = None, 
    history: Optional[str] = None, 
    instructions: Optional[str] = None, 
    db: Session = Depends(get_db),
    services: AIServices = Depends(get_ai_services)
):
    """Fetch a question for simulation/testing using deterministic selection and live generation."""
    try:
        # 1. Use manual instructions if provided (from UI), else fetch latest from DB
        if instructions:
            services.bot.instructions = instructions
        else:
            quiz_config = db.query(Quiz).filter_by(course_id=course_id).order_by(Quiz.id.desc()).first()
            services.bot.instructions = quiz_config.instructions if quiz_config else None
        
        # 2. Live Selection
        exclude_list = [int(i) for i in exclude_ids.split(",") if i.isdigit()] if exclude_ids else None
        chunk, author = services.planner.select_next_topic(course_id=course_id, used_chunk_ids=exclude_list, instructions=instructions)
        if not chunk:
            raise HTTPException(status_code=404, detail="No unique topics found. Review syllabus or clear history.")

        # 3. Live Generation
        # For simulation, we can also pass history turns if we want full chat awareness
        history_turns = []
        if history:
            # history is comma-separated pairs like "q1|a1,q2|a2"
            pairs = history.split(",")
            for p in pairs:
                if "|" in p:
                    q, a = p.split("|", 1)
                    history_turns.append({"role": "bot", "text": q})
                    history_turns.append({"role": "user", "text": a})

        question = services.bot.generate_single_question(chunk, course_id=course_id, author=author, history_turns=history_turns)
        
        if question:
            return {
                "id": question.id, 
                "text": question.question_text, 
                "answer": question.ideal_answer, 
                "status": question.status.value,
                "context": clean_context_label(question.subsection.section.title) if question.subsection else "Assessment Simulation"
            }
    except HTTPException:
        # Re-raise known HTTP exceptions (like 404 No topics)
        raise
    except (Exception, StopIteration) as e:
        print(f"[!] Simulation Error: {e}")
        raise HTTPException(status_code=500, detail="AI generation interrupted. Please try again.")

@app.post("/professor/questions/{question_id}/rank")
def rank_question(question_id: int, interaction: str, db: Session = Depends(get_db)):
    """Rank a question (like/dislike) during simulation."""
    question = db.query(Question).get(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
        
    if interaction == "like":
        question.upvotes += 1
    elif interaction == "dislike":
        question.downvotes += 1
        
    db.commit()
    return {"status": "Ranked", "upvotes": question.upvotes, "downvotes": question.downvotes}

@app.get("/professor/quiz/draft/{course_id}")
def get_quiz_draft(course_id: int, db: Session = Depends(get_db)):
    """Fetch the latest unfinalized quiz (draft) for a course."""
    quiz = db.query(Quiz).filter_by(course_id=course_id, is_finalized=0).order_by(Quiz.id.desc()).first()
    if not quiz:
        return {"draft": None}
    return {
        "draft": {
            "id": quiz.id,
            "title": quiz.title,
            "description": quiz.description,
            "duration_minutes": quiz.duration_minutes,
            "total_marks": quiz.total_marks,
            "total_questions": quiz.total_questions,
            "instructions": quiz.instructions,
            "allow_audio": quiz.allow_audio,
            "ai_eval_enabled": quiz.ai_eval_enabled,
            "ai_eval_rubric": quiz.ai_eval_rubric
        }
    }

@app.post("/professor/quiz/draft/{course_id}")
def save_quiz_draft(course_id: int, data: dict, db: Session = Depends(get_db)):
    """Upserts a draft quiz for the course."""
    quiz = db.query(Quiz).filter_by(course_id=course_id, is_finalized=0).order_by(Quiz.id.desc()).first()
    
    if not quiz:
        quiz = Quiz(course_id=course_id, is_finalized=0)
        db.add(quiz)
        
    quiz.title = data.get("title", quiz.title)
    quiz.description = data.get("description", quiz.description)
    quiz.duration_minutes = data.get("duration_minutes", quiz.duration_minutes)
    quiz.total_marks = data.get("total_marks", quiz.total_marks)
    quiz.total_questions = data.get("total_questions", quiz.total_questions)
    quiz.instructions = data.get("instructions", quiz.instructions)
    quiz.allow_audio = data.get("allow_audio", quiz.allow_audio)
    quiz.ai_eval_enabled = data.get("ai_eval_enabled", quiz.ai_eval_enabled)
    quiz.ai_eval_rubric = data.get("ai_eval_rubric", quiz.ai_eval_rubric)
    
    db.commit()
    return {"status": "saved", "quiz_id": quiz.id}

@app.post("/professor/quiz/create")
def create_exam_config(course_id: int, title: str, duration: int, total_marks: int, total_questions: int = 5, instructions: Optional[str] = None, allow_audio: bool = True, ai_eval_enabled: bool = False, ai_eval_rubric: Optional[str] = None, db: Session = Depends(get_db)):
    """Saves or updates the exam configuration before generation."""
    quiz = db.query(Quiz).filter_by(course_id=course_id, is_finalized=0).order_by(Quiz.id.desc()).first()
    if not quiz:
        quiz = Quiz(course_id=course_id, is_finalized=0)
        db.add(quiz)
        
    quiz.title = title
    quiz.duration_minutes = duration
    quiz.total_marks = total_marks
    quiz.total_questions = total_questions
    quiz.instructions = instructions
    quiz.allow_audio = allow_audio
    quiz.ai_eval_enabled = ai_eval_enabled
    quiz.ai_eval_rubric = ai_eval_rubric
    db.commit()
    return {"quiz_id": quiz.id}

@app.put("/professor/quiz/{quiz_id}")
def update_quiz_details(quiz_id: int, data: dict, db: Session = Depends(get_db)):
    """Update assessment configuration."""
    quiz = db.query(Quiz).get(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    quiz.title = data.get("title", quiz.title)
    quiz.duration_minutes = data.get("duration", quiz.duration_minutes)
    quiz.instructions = data.get("instructions", quiz.instructions)
    if "ai_eval_enabled" in data:
        quiz.ai_eval_enabled = data["ai_eval_enabled"]
    if "ai_eval_rubric" in data:
        quiz.ai_eval_rubric = data["ai_eval_rubric"]
    
    db.commit()
    return {"status": "updated"}

@app.post("/professor/quiz/{quiz_id}/finalize")
def finalize_quiz(quiz_id: int, password: str, db: Session = Depends(get_db)):
    """Locks the quiz and sets the access password."""
    quiz = db.query(Quiz).get(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    quiz.password = password
    quiz.is_finalized = 1
    db.commit()
    return {"status": "finalized"}

@app.post("/professor/quiz/{quiz_id}/password")
def update_quiz_password(quiz_id: int, password: str, db: Session = Depends(get_db)):
    """Updates the access password for a quiz."""
    quiz = db.query(Quiz).get(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    quiz.password = password
    db.commit()
    return {"status": "updated", "password": password}

@app.delete("/professor/quiz/{quiz_id}")
def delete_quiz(quiz_id: int, db: Session = Depends(get_db)):
    """Deletes an assessment and its dependencies."""
    quiz = db.query(Quiz).get(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    db.delete(quiz)
    db.commit()
    return {"status": "deleted"}

@app.get("/professor/quiz/{quiz_id}")
def get_quiz_details(quiz_id: int, db: Session = Depends(get_db)):
    """Fetch details for a specific quiz."""
    quiz = db.query(Quiz).get(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return {
        "id": quiz.id,
        "title": quiz.title,
        "course_id": quiz.course_id,
        "duration_minutes": quiz.duration_minutes,
        "total_marks": quiz.total_marks,
        "total_questions": quiz.total_questions,
        "is_finalized": quiz.is_finalized == 1,
        "instructions": quiz.instructions,
        "ai_eval_enabled": quiz.ai_eval_enabled or False,
        "ai_eval_rubric": quiz.ai_eval_rubric
    }

@app.get("/professor/quiz/{quiz_id}/student/{enrollment_id}/messages")
def get_student_transcript_messages(quiz_id: int, enrollment_id: str, db: Session = Depends(get_db)):
    """Fetch the full conversation history for a specific student in a quiz."""
    transcripts = db.query(Transcript).filter_by(
        quiz_id=quiz_id,
        enrollment_id=enrollment_id
    ).order_by(Transcript.created_at).all()
    
    messages = []
    for t in transcripts:
        # Each transcript record represents one Q&A turn
        messages.append({
            "role": "bot",
            "text": t.question.question_text if t.question else "N/A",
            "type": "question"
        })
        # Parse AI eval results if available
        ai_eval = None
        if t.ai_eval_results:
            try:
                ai_eval = json.loads(t.ai_eval_results)
            except json.JSONDecodeError:
                pass
        messages.append({
            "role": "user",
            "text": t.student_answer,
            "type": "answer",
            "question_id": t.question_id,
            "ai_eval_results": ai_eval
        })
        
    return messages

@app.get("/professor/quiz/{quiz_id}/student/{enrollment_id}/ai-evaluation")
def get_student_ai_evaluation(quiz_id: int, enrollment_id: str, db: Session = Depends(get_db)):
    """Returns the aggregated rubric evaluation summary for a student's entire exam."""
    quiz = db.query(Quiz).get(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    if not quiz.ai_eval_enabled:
        return {"enabled": False}
    
    transcripts = db.query(Transcript).filter_by(
        quiz_id=quiz_id,
        enrollment_id=enrollment_id
    ).order_by(Transcript.created_at).all()
    
    per_question = []
    grand_total_awarded = 0
    grand_total_max = 0
    
    for i, t in enumerate(transcripts):
        q_text = t.question.question_text if t.question else "N/A"
        if t.ai_eval_results:
            try:
                eval_data = json.loads(t.ai_eval_results)
                awarded = int(eval_data.get("total_awarded", 0))
                max_marks = int(eval_data.get("total_max", 0))
                grand_total_awarded += awarded
                grand_total_max += max_marks
                per_question.append({
                    "question_number": i + 1,
                    "question_text": q_text,
                    "student_answer": t.student_answer,
                    "criteria_scores": eval_data.get("criteria_scores", []),
                    "total_awarded": awarded,
                    "total_max": max_marks,
                    "overall_remark": eval_data.get("overall_remark", "")
                })
            except json.JSONDecodeError:
                per_question.append({
                    "question_number": i + 1,
                    "question_text": q_text,
                    "error": "Failed to parse evaluation"
                })
        else:
            per_question.append({
                "question_number": i + 1,
                "question_text": q_text,
                "note": "No rubric evaluation recorded"
            })
    
    return {
        "enabled": True,
        "per_question": per_question,
        "grand_total_awarded": grand_total_awarded,
        "grand_total_max": grand_total_max
    }

# --- Student Endpoints ---
@app.get("/student/quiz/{quiz_id}/meta")
def get_quiz_meta(quiz_id: int, db: Session = Depends(get_db)):
    """Fetch basic info about a quiz for students (title, duration)."""
    quiz = db.query(Quiz).get(quiz_id)
    if not quiz or not quiz.is_finalized:
        raise HTTPException(status_code=404, detail="Quiz not found or not active")
    return {
        "title": quiz.title,
        "duration_minutes": quiz.duration_minutes,
        "total_questions": quiz.total_questions,
        "allow_audio": quiz.allow_audio
    }


@app.post("/student/quiz/start/{quiz_id}")
def start_quiz(quiz_id: int, data: dict, db: Session = Depends(get_db)):
    """Starts a quiz session using the QuizManager."""
    quiz = db.query(Quiz).get(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Check password if quiz is finalized
    if quiz.is_finalized and quiz.password:
        provided_password = data.get("password")
        if provided_password != quiz.password:
            raise HTTPException(status_code=401, detail="Invalid access password")

    return {"quiz_id": quiz_id, "status": "authorized"}

@app.put("/student/quiz/{quiz_id}/response")
def update_student_response(
    quiz_id: int, 
    data: dict, 
    db: Session = Depends(get_db)
):
    """Updates a student's previous response WITHOUT triggering AI generation."""
    from ..database.models.transcript import Transcript
    
    q_id = data.get('question_id')
    e_id = data.get('enrollment_id')
    
    if not q_id or not e_id:
        raise HTTPException(status_code=400, detail="Missing question_id or enrollment_id")

    transcript = db.query(Transcript).filter_by(
        quiz_id=quiz_id,
        question_id=int(q_id) if q_id is not None else 0,
        enrollment_id=str(e_id)
    ).first()
    
    if not transcript:
        print(f"[*] Update Failed: No transcript found for Quiz {quiz_id}, Question {q_id}, Student {e_id}")
        raise HTTPException(status_code=404, detail="Original response not found in database.")
        
    transcript.student_answer = data.get('new_answer')
    db.commit()
    return {"status": "Updated", "message": "Response updated successfully"}

@app.post("/student/quiz/{quiz_id}/submit")
def submit_answer(
    quiz_id: int, 
    data: dict, 
    db: Session = Depends(get_db),
    services: AIServices = Depends(get_ai_services)
):
    print(f"DEBUG: Processing answer for Quiz {quiz_id}, Question {data.get('question_id')}, Student {data.get('enrollment_id')}")
    try:
        manager = QuizManager(db, services.eval_svc)
        
        result = manager.submit_answer(
            quiz_id=quiz_id,
            question_id=data.get("question_id"),
            answer_text=data.get("answer"),
            student_name=data.get("student_name"),
            enrollment_id=data.get("enrollment_id")
        )
        return result
    except (Exception, StopIteration) as e:
        print(f"CRITICAL ERROR in submit_answer: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="The evaluation service is temporarily busy. Please try resubmitting.")

@app.get("/student/quiz/{quiz_id}/next-question")
def get_student_next_question(
    quiz_id: int, 
    enrollment_id: str, 
    student_name: Optional[str] = None, 
    exclude_ids: Optional[str] = None, 
    db: Session = Depends(get_db),
    services: AIServices = Depends(get_ai_services)
):
    try:
        # Step 1: Detect Session State & Locking
        quiz = db.query(Quiz).get(quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        if quiz.is_processing:
            raise HTTPException(status_code=429, detail="A question is already being generated. Please wait.")
        
        quiz.is_processing = True
        db.commit()

        try:
            # Re-fetch records once lock is acquired
            answered_count = db.query(Transcript).filter_by(enrollment_id=enrollment_id, quiz_id=quiz_id).count()
            
            manager = QuizManager(db, services.eval_svc)
            
            # Correctly handle turn_number for QuizGraph
            res = manager.get_next_question(
                quiz_id=quiz_id,
                enrollment_id=enrollment_id,
                student_name=student_name,
                turn_number=answered_count + 1,
                total_questions=quiz.total_questions or 10
            )

            if "error" in res:
                raise HTTPException(status_code=500, detail=res["error"])

            return {
                "id": res["question_id"],
                "text": res["question_text"],
                "answer": "HIDDEN_DURING_QUIZ",
                "context": res["concept_name"] or "Assessment",
                "session_phase": res["session_phase"],
                "bloom_phase": res["bloom_phase"]
            }

        finally:
            # Always release lock
            quiz = db.query(Quiz).get(quiz_id)
            if quiz:
                quiz.is_processing = False
                db.commit()
    except HTTPException:
        raise
    except (Exception, StopIteration) as e:
        print(f"[!] get_student_next_question Error: {e}")
        raise HTTPException(status_code=500, detail="The tutor is thinking... please refresh in a moment.")

# --- Audit & Management Endpoints ---

@app.get("/professor/quiz/{quiz_id}/transcripts")
def list_student_transcripts(quiz_id: int, db: Session = Depends(get_db)):
    """List all students who have taken this quiz."""
    transcripts = db.query(Transcript).filter_by(quiz_id=quiz_id).all()
    # Group by student to show unique participants
    participants = {}
    for t in transcripts:
        # Robust key generation: prefer enrollment_id, fallback to name, fallback to ID
        eid = t.enrollment_id or "Unknown_ID"
        name = t.student_name or "Unknown_Student"
        key = f"{eid}_{name}"
        
        if key not in participants:
            participants[key] = {
                "name": name,
                "enrollment_id": t.enrollment_id,
                "completed_at": t.created_at,
                "id": t.id # Use one transcript ID as reference
            }
    return list(participants.values())

@app.get("/professor/transcript/{transcript_id}/export")
def export_transcript(transcript_id: int, db: Session = Depends(get_db)):
    """Exports the full dialogue of a student's assessment session as a TXT file."""
    base_t = db.query(Transcript).get(transcript_id)
    if not base_t:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    # Fetch all interactions for this specific student in this quiz
    # Use robust filtering: ensure we catch all turns for this student enrollment even if IDs vary slightly
    all_interactions = db.query(Transcript).filter(
        Transcript.quiz_id == base_t.quiz_id,
        Transcript.enrollment_id == base_t.enrollment_id
    ).order_by(Transcript.created_at).all()
    
    content = f"--- AIssociate ASSESSMENT TRANSCRIPT ---\n"
    content += f"STUDENT: {base_t.student_name}\n"
    content += f"ENROLLMENT: {base_t.enrollment_id}\n"
    content += f"QUIZ ID: {base_t.quiz_id}\n"
    content += f"DATE: {base_t.created_at}\n"
    content += f"{'='*40}\n\n"
    
    for i, t in enumerate(all_interactions):
        content += f"Q{i+1}: {t.question.question_text if t.question else 'N/A'}\n"
        content += f"STUDENT: {t.student_answer}\n"
        if t.ai_eval_results:
            try:
                eval_data = json.loads(t.ai_eval_results)
                content += f"AI EVALUATION:\n"
                for cs in eval_data.get("criteria_scores", []):
                    content += f"  - {cs['name']}: {cs.get('awarded', 0)}/{cs.get('max_marks', 0)} — {cs.get('remark', '')}\n"
                content += f"  TOTAL: {eval_data.get('total_awarded', 0)}/{eval_data.get('total_max', 0)}\n"
                content += f"  REMARK: {eval_data.get('overall_remark', '')}\n"
            except json.JSONDecodeError:
                pass
        content += f"{'-'*40}\n"
    
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=transcript_{base_t.enrollment_id}.txt"}
    )

@app.get("/professor/transcript/{transcript_id}/export-pdf")
def export_transcript_pdf(transcript_id: int, db: Session = Depends(get_db)):
    """Exports the full dialogue of a student's assessment session as a PDF file."""
    import fitz # type: ignore
    import io
    
    base_t = db.query(Transcript).get(transcript_id)
    if not base_t:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    # Fetch all interactions
    all_interactions = db.query(Transcript).filter(
        Transcript.quiz_id == base_t.quiz_id,
        Transcript.enrollment_id == base_t.enrollment_id
    ).order_by(Transcript.created_at).all()
    
    # Create PDF document
    doc = fitz.open()
    page = doc.new_page()
    
    # Initial cursor position
    cursor_y = 50
    page_height = 800
    margin = 50
    
    def check_page_break(doc, page, y, needed_height):
        """Adds a new page if content exceeds height."""
        if y + needed_height > page_height:
            page = doc.new_page()
            return page, 50 # Reset y to top margin
        return page, y

    def write_wrapped_text(doc, page, y, text, fontsize=11, color=(0,0,0), bold=False):
        """Writes text with word wrapping and pagination."""
        fontname = "helv"  # Base font
        line_height = fontsize + 4
        rect_width = 500
        x = 50
        
        # Approximate width calculation or character splitting
        # PyMuPDF's insert_text is simple. Use fitz.TextLength for accurate width?
        # For simplicity and speed without complex font loading:
        # We will split by words and build lines.
        
        paragraphs = text.split('\n')
        for p in paragraphs:
            words = p.split()
            current_line = ""
            for word in words:
                test_line = current_line + " " + word if current_line else word
                # Fast width check: ~0.5 * fontsize * length (heuristic) 
                # OR use fitz.get_text_length(test_line, fontname=fontname, fontsize=fontsize)
                w = fitz.get_text_length(test_line, fontname=fontname, fontsize=fontsize)
                if w < rect_width:
                    current_line = test_line
                else:
                    # Draw current line
                    page, y = check_page_break(doc, page, y, line_height)
                    page.insert_text((x, y), current_line, fontsize=fontsize, fontname=fontname, color=color)
                    y += line_height
                    current_line = word # Start new line with word
            
            # Draw remaining line
            if current_line:
                page, y = check_page_break(doc, page, y, line_height)
                page.insert_text((x, y), current_line, fontsize=fontsize, fontname=fontname, color=color)
                y += line_height
        
        return page, y

    # Header
    page.insert_text((50, cursor_y), "AIssociate ASSESSMENT TRANSCRIPT", fontsize=16, color=(0, 0, 1))
    cursor_y += 30
    
    metadata = [
        f"STUDENT: {base_t.student_name}",
        f"ENROLLMENT: {base_t.enrollment_id}",
        f"QUIZ ID: {base_t.quiz_id}",
        f"DATE: {base_t.created_at.strftime('%Y-%m-%d %H:%M:%S') if base_t.created_at else 'N/A'}"
    ]
    
    for line in metadata:
        page, cursor_y = check_page_break(doc, page, cursor_y, 20)
        page.insert_text((50, cursor_y), line, fontsize=11)
        cursor_y += 20
        
    cursor_y += 10
    page.insert_text((50, cursor_y), "=" * 80, fontsize=10)
    cursor_y += 30
    
    # Content
    for i, t in enumerate(all_interactions):
        # spacer
        cursor_y += 10
        
        # Question
        q_label = f"Q{i+1}: "
        q_text = t.question.question_text if t.question else 'N/A'
        
        page, cursor_y = write_wrapped_text(doc, page, cursor_y, q_label + q_text, fontsize=11, bold=True)
        cursor_y += 10
        
        # Answer
        a_label = "STUDENT ANSWER: "
        a_text = t.student_answer or "[No Answer]"
        page, cursor_y = write_wrapped_text(doc, page, cursor_y, a_label + a_text, fontsize=10, color=(0.2, 0.2, 0.2))
        
        cursor_y += 10
        page, cursor_y = check_page_break(doc, page, cursor_y, 20)
        page.draw_line(fitz.Point(50, cursor_y), fitz.Point(550, cursor_y), color=(0.8, 0.8, 0.8), width=0.5)
        cursor_y += 20
        
    # Save to stream
    pdf_bytes = doc.tobytes()
    doc.close()
    
    from fastapi.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=transcript_{base_t.enrollment_id}.pdf"}
    )

# --- Voice Chat Endpoints ---

@app.post("/api/voice-chat/general")
async def voice_chat_general(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    General conversational voice chat.
    Pipeline: Speech -> STT -> Math Norm -> LLM -> TTS -> Audio
    """
    temp_audio_path = f"temp_voice_{file.filename}"
    try:
        # 1. Save uploaded audio
        with open(temp_audio_path, "wb") as f:
            f.write(await file.read())
        
        # 2. Transcribe (includes Math Normalization)
        user_text = voice_service.transcribe(temp_audio_path)
        if not user_text:
            return JSONResponse(status_code=400, content={"message": "Could not transcribe audio"})
            
        print(f"User said: {user_text}")
        
        # 3. Get LLM Response
        # For general chat, we can use a simple prompt or context
        system_prompt = "You are a helpful AI tutor. Keep responses concise and conversational."
        # Use existing LLM service
        ai_response_text = llm.generate_content(user_text, system_prompt=system_prompt)
        
        # Clean response if it has errors
        if ai_response_text.startswith("ERROR"):
            ai_response_text = "I'm having trouble connecting to my brain right now. Please try again."
            
        print(f"AI response: {ai_response_text}")
        
        # 4. Synthesize Speech
        output_audio_path = voice_service.synthesize(ai_response_text)
        
        if not output_audio_path or not os.path.exists(output_audio_path):
             return JSONResponse(status_code=500, content={"message": "Failed to generate speech"})
             
        # 5. Return JSON with text and audio (base64)
        with open(output_audio_path, "rb") as audio_file:
            audio_base64 = base64.b64encode(audio_file.read()).decode('utf-8')
            
        # Clean up
        try:
            os.remove(output_audio_path)
        except:
            pass
            
        return {
            "user_text": user_text,
            "ai_text": ai_response_text,
            "audio_base64": audio_base64,
            "format": "mp3"
        }
        
    except Exception as e:
        print(f"Error in voice chat: {e}")
        return JSONResponse(status_code=500, content={"message": str(e)})
    finally:
        # Clean up input file
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except:
                pass

class SynthesizeRequest(BaseModel):
    text: str

@app.post("/api/voice-chat/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe an audio file and return the text."""
    temp_audio_path = f"temp_transcribe_{file.filename}"
    try:
        with open(temp_audio_path, "wb") as f:
            f.write(await file.read())
            
        user_text = voice_service.transcribe(temp_audio_path)
        if not user_text:
            return JSONResponse(status_code=400, content={"message": "Could not transcribe audio"})
            
        return {"user_text": user_text}
    except Exception as e:
        print(f"Error in transcription: {e}")
        return JSONResponse(status_code=500, content={"message": str(e)})
    finally:
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except:
                pass

@app.post("/api/voice-chat/synthesize")
def synthesize_text(request: SynthesizeRequest):
    """Synthesize text into speech and return the audio file."""
    try:
        output_audio_path = voice_service.synthesize(request.text)
        if not output_audio_path or not os.path.exists(output_audio_path):
             return JSONResponse(status_code=500, content={"message": "Failed to generate speech"})
             
        # Return the audio file and delete it after sending
        return FileResponse(
            output_audio_path, 
            media_type="audio/mpeg", 
            background=BackgroundTask(os.remove, output_audio_path)
        )
    except Exception as e:
        print(f"Error in synthesis: {e}")
        return JSONResponse(status_code=500, content={"message": str(e)})
