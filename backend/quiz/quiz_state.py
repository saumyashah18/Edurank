from typing import TypedDict, Optional, List

class QuizState(TypedDict):
    # Session identifiers
    student_id: str
    quiz_id: int
    course_id: int
#
    # Current concept being tested
    current_concept_id: Optional[int]
    current_concept_name: Optional[str]
    current_bloom_phase: int            # 1-5

    # Current question
    current_question_id: Optional[int]
    current_question_text: Optional[str]
    current_chunk_id: Optional[int]

    # Current answer (set when student submits)
    current_answer: Optional[str]

    # Last evaluation result
    last_score: Optional[float]
    last_misconception: Optional[str]
    last_recommended_action: Optional[str]

    # Session tracking
    turn_number: int
    total_questions: int
    session_phase: str                  # "opening", "middle", "closing"
    used_chunk_ids: List[int]
    instructions: Optional[str]         # Professor's system instructions for topic filtering
    selected_document_ids: Optional[List[int]] # Professor-selected specific documents for this assessment

    # Output fields (what gets returned to the HTTP layer)
    output_question_text: Optional[str]
    output_ideal_answer: Optional[str]
    output_hint: Optional[str]
    output_bloom_phase: int
    output_concept_name: Optional[str]
    output_session_phase: str
    output_error: Optional[str]
