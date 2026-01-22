import re

path = 'backend/api/main.py'
with open(path, 'r') as f:
    content = f.read()

# Match the entire function from decorator to return
pattern = r'@app\.get\("/professor/simulate/next"\)\ndef get_next_simulation_question\(.*?\):.*?return \{.*?\}'
new_func = """@app.get("/professor/simulate/next")
def get_next_simulation_question(course_id: int, exclude_ids: str = "", history: str = "", db: Session = Depends(get_db)):
    \"\"\"Fetch a question for simulation/testing with variety and adaptive history support.\"\"\"
    # Parse history if provided (format: q|a,q|a)
    parsed_history = []
    if history:
        for turn in history.split(","):
            if "|" in turn:
                q, a = turn.split("|", 1)
                parsed_history.append({"q": q, "a": a})

    # Always use the Adaptive Bot Strategy for Simulation
    planner = TopicPlanner(db)
    rag = RAGService(db, Embedder(db))
    bot = ProfessorBot(db, rag, planner)
    
    # Fetch instructions for this course (from existing quiz)
    quiz_config = db.query(Quiz).filter_by(course_id=course_id).order_by(Quiz.id.desc()).first()
    bot.instructions = quiz_config.instructions if quiz_config else None
    
    # generate_single_question now handles Phase 0 (Greeting) and Graph-RAG
    question = bot.generate_single_question(course_id, history=parsed_history, is_simulation=True)
    
    if question:
        return {
            "id": question.id, 
            "text": question.question_text, 
            "answer": question.ideal_answer, 
            "status": question.status.value,
            "context": f"{question.subsection.section.chapter.title} > {question.subsection.section.title}" if question.subsection else "Adaptive Simulation"
        }

    raise HTTPException(status_code=404, detail="The bot was unable to generate a question. Please ensure syllabus data exists.")"""

# Use a more liberal match for the whole function body
start_marker = '@app.get("/professor/simulate/next")'
end_marker = '    return {\n        "id": question.id, \n        "text": question.question_text, \n        "answer": question.ideal_answer, \n        "status": question.status.value,\n        "context": f"{question.subsection.section.chapter.title} > {question.subsection.section.title}"\n    }'

# Let's try string split since we know the lines
lines = content.split('\n')
start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if '@app.get("/professor/simulate/next")' in line:
        start_idx = i
    if start_idx != -1 and i > start_idx and '"context": f"{question.subsection.section.chapter.title} > {question.subsection.section.title}"' in line:
        end_idx = i + 2 # capture the closing } and following newline if any

if start_idx != -1 and end_idx != -1:
    new_content = '\n'.join(lines[:start_idx]) + '\n' + new_func + '\n' + '\n'.join(lines[end_idx:])
    with open(path, 'w') as f:
        f.write(new_content)
    print("Successfully patched main.py")
else:
    print(f"Failed to find markers: start={start_idx}, end={end_idx}")
