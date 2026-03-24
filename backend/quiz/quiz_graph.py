from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session
from sqlalchemy import func
from .quiz_state import QuizState
from .planner import TopicPlanner
from .professor_bot import ProfessorBot
from .student_model import StudentModelUpdater
from ..rag.embedder import RAGService, Embedder
from ..rag.evaluation import EvaluationService
from ..database.models.chunk import Chunk
from ..database.models.concept import Concept, ConceptChunk
from ..database.models.transcript import Quiz

class QuizGraph:
    def __init__(self, db: Session):
        self.db = db
        self._build_graph()

    def _build_graph(self):
        """Builds the LangGraph state machine."""
        graph = StateGraph(QuizState)

        graph.add_node("arc_node", self._arc_node)
        graph.add_node("plan_node", self._plan_node)
        graph.add_node("generate_node", self._generate_node)
        graph.add_node("evaluate_node", self._evaluate_node)
        graph.add_node("hint_node", self._hint_node)
        graph.add_node("update_model_node", self._update_model_node)

        # Entry point for next-question flow
        graph.set_entry_point("arc_node")

        # Edges from arc_node
        graph.add_edge("arc_node", "plan_node")

        # Edges from plan_node
        graph.add_edge("plan_node", "generate_node")

        # Edges from generate_node → END (question ready for HTTP response)
        graph.add_edge("generate_node", END)

        # No direct edges for evaluate_node in the main graph 
        # because run_evaluate uses its own compiled subflow.

        self.graph = graph.compile()

        # Pre-compile the evaluate subflow (evaluate → hint? → update_model → END)
        eval_graph = StateGraph(QuizState)
        eval_graph.add_node("evaluate_node", self._evaluate_node)
        eval_graph.add_node("hint_node", self._hint_node)
        eval_graph.add_node("update_model_node", self._update_model_node)
        eval_graph.set_entry_point("evaluate_node")
        eval_graph.add_conditional_edges(
            "evaluate_node",
            self._route_after_evaluate,
            {"hint": "hint_node", "update": "update_model_node"}
        )
        eval_graph.add_edge("hint_node", "update_model_node")
        eval_graph.add_edge("update_model_node", END)
        self.eval_graph = eval_graph.compile()

    # ── NODE: arc_node ──────────────────────────────────────────────
    def _arc_node(self, state: QuizState) -> QuizState:
        """
        Determines session_phase and bloom_phase from turn_number.
        Updates state. No DB calls.
        """
        turn = state["turn_number"]
        total = state["total_questions"]

        opening_cutoff = max(1, int(total * 0.2))
        closing_cutoff = total - max(1, int(total * 0.2))

        if turn <= opening_cutoff:
            session_phase = "opening"
            bloom_phase = 1
        elif turn >= closing_cutoff:
            session_phase = "closing"
            bloom_phase = 1
        else:
            session_phase = "middle"
            bloom_phase = state.get("current_bloom_phase", 2)

        return {**state, "session_phase": session_phase, "current_bloom_phase": bloom_phase}

    # ── NODE: plan_node ─────────────────────────────────────────────
    def _plan_node(self, state: QuizState) -> QuizState:
        """
        Selects next concept and chunk using TopicPlanner.
        If last_recommended_action == "drop_to_prerequisite": find prereq concept chunk.
        If last_recommended_action == "retry_rephrase": reuse current_chunk_id.
        Otherwise: call planner.select_next_topic() normally.
        """
        planner = TopicPlanner(self.db)
        action = state.get("last_recommended_action")
        course_id = state["course_id"]
        student_id = state["student_id"]
        quiz_id = state["quiz_id"]

        chunk = None
        concept_name = None
        concept_id = None
        bloom_phase = state["current_bloom_phase"]

        # retry_rephrase: stay on same chunk
        if action == "retry_rephrase" and state.get("current_chunk_id"):
            chunk = self.db.query(Chunk).get(state["current_chunk_id"])
            concept_id = state.get("current_concept_id")
            concept_name = state.get("current_concept_name")

        # drop_to_prerequisite: find prereq of current concept
        elif action == "drop_to_prerequisite" and state.get("current_concept_id"):
            from ..database.models.concept import ConceptRelation
            prereq_rel = self.db.query(ConceptRelation).filter_by(
                to_concept_id=state["current_concept_id"],
                relation_type="prerequisite"
            ).first()
            if prereq_rel:
                prereq_concept = self.db.query(Concept).get(prereq_rel.from_concept_id)
                if prereq_concept:
                    concept_id = prereq_concept.id
                    concept_name = prereq_concept.name
                    cc = self.db.query(ConceptChunk).filter_by(concept_id=concept_id).first()
                    if cc:
                        chunk = self.db.query(Chunk).get(cc.chunk_id)

        # Default: use planner
        if chunk is None:
            chunk, author = planner.select_next_topic(
                course_id=course_id,
                enrollment_id=student_id,
                quiz_id=quiz_id,
                used_chunk_ids=state.get("used_chunk_ids", [])
            )
            if chunk:
                cc = self.db.query(ConceptChunk).filter_by(chunk_id=chunk.id).first()
                if cc:
                    concept = self.db.query(Concept).get(cc.concept_id)
                    if concept:
                        concept_id = concept.id
                        concept_name = concept.name
                        bloom_phase = planner.get_current_bloom_phase(student_id, quiz_id, concept.id)

        if chunk is None:
            return {**state, "output_error": "No content available for this course."}

        used = list(state.get("used_chunk_ids", []))
        if chunk.id not in used:
            used.append(chunk.id)

        return {
            **state,
            "current_chunk_id": chunk.id,
            "current_concept_id": concept_id,
            "current_concept_name": concept_name,
            "current_bloom_phase": bloom_phase,
            "used_chunk_ids": used,
            "output_error": None
        }

    # ── NODE: generate_node ─────────────────────────────────────────
    def _generate_node(self, state: QuizState) -> QuizState:
        """
        Calls ProfessorBot to generate a question from current_chunk_id.
        Writes output fields that the HTTP layer reads.
        """
        if state.get("output_error"):
            return state

        chunk = self.db.query(Chunk).get(state["current_chunk_id"])
        if not chunk:
            return {**state, "output_error": "Chunk not found."}

        quiz = self.db.query(Quiz).get(state["quiz_id"])
        embedder = Embedder(self.db)
        rag = RAGService(self.db, embedder)
        planner = TopicPlanner(self.db)
        bot = ProfessorBot(self.db, rag, planner)
        bot.instructions = quiz.instructions if quiz else None

        question = bot.generate_single_question(
            chunk=chunk,
            course_id=state["course_id"],
            history_turns=[],
            turn_number=state["turn_number"],
            bloom_phase=state["current_bloom_phase"],
            misconception=state.get("last_misconception") if state["session_phase"] == "closing" else None,
            concept_name=state.get("current_concept_name")
        )

        if not question:
            return {**state, "output_error": "Question generation failed."}

        return {
            **state,
            "current_question_id": question.id,
            "current_question_text": question.question_text,
            "output_question_text": question.question_text,
            "output_ideal_answer": question.ideal_answer,
            "output_hint": None,
            "output_bloom_phase": state["current_bloom_phase"],
            "output_concept_name": state.get("current_concept_name"),
            "output_session_phase": state["session_phase"],
            "output_error": None
        }

    # ── NODE: evaluate_node ─────────────────────────────────────────
    def _evaluate_node(self, state: QuizState) -> QuizState:
        """
        Evaluates current_answer against current_question.
        Updates last_score, last_misconception, last_recommended_action.
        """
        from ..database.models.question import Question
        question = self.db.query(Question).get(state["current_question_id"])
        if not question:
            return {**state, "last_score": 0.0}

        quiz = self.db.query(Quiz).get(state["quiz_id"])
        eval_service = EvaluationService(self.db, RAGService(self.db, Embedder(self.db)))

        result = eval_service.evaluate_answer(
            question_text=question.question_text,
            student_answer=state["current_answer"],
            ideal_answer=question.ideal_answer,
            instructions=quiz.instructions if quiz else None
        )

        return {
            **state,
            "last_score": result.get("score", 0.0),
            "last_misconception": result.get("misconception"),
            "last_recommended_action": result.get("recommended_action"),
        }

    # ── NODE: hint_node ─────────────────────────────────────────────
    def _hint_node(self, state: QuizState) -> QuizState:
        """
        Generates a Socratic hint when score < 0.4.
        Writes hint to output_hint.
        """
        chunk = self.db.query(Chunk).get(state.get("current_chunk_id"))
        if not chunk:
            return state

        quiz = self.db.query(Quiz).get(state["quiz_id"])
        embedder = Embedder(self.db)
        rag = RAGService(self.db, embedder)
        planner = TopicPlanner(self.db)
        bot = ProfessorBot(self.db, rag, planner)
        bot.instructions = quiz.instructions if quiz else None

        hint = bot.generate_hint(
            question_text=state.get("current_question_text", ""),
            chunk_content=chunk.content,
            misconception=state.get("last_misconception")
        )

        return {**state, "output_hint": hint}

    # ── NODE: update_model_node ─────────────────────────────────────
    def _update_model_node(self, state: QuizState) -> QuizState:
        """
        Calls StudentModelUpdater to update student_concept_states.
        Non-fatal — logs and continues on error.
        """
        try:
            updater = StudentModelUpdater(self.db)
            updater.update(
                student_id=state["student_id"],
                quiz_id=state["quiz_id"],
                course_id=state["course_id"],
                score=state.get("last_score", 0.0),
                misconception=state.get("last_misconception"),
                recommended_action=state.get("last_recommended_action"),
                concept_tags=[state["current_concept_name"]] if state.get("current_concept_name") else []
            )
        except Exception as e:
            print(f"[QuizGraph] update_model_node non-fatal error: {e}")

        return state

    # ── CONDITIONAL EDGE ────────────────────────────────────────────
    def _route_after_evaluate(self, state: QuizState) -> str:
        """Routes to hint_node if score < 0.4, otherwise straight to update."""
        if state.get("last_score", 1.0) < 0.4:
            return "hint"
        return "update"

    # ── PUBLIC INTERFACE ────────────────────────────────────────────
    def run_next_question(self, state: QuizState) -> QuizState:
        """
        Entry point for /next-question.
        Runs: arc_node → plan_node → generate_node → END
        """
        return self.graph.invoke(state)

    def run_evaluate(self, state: QuizState) -> QuizState:
        """
        Entry point for /submit.
        Runs: evaluate_node → (hint_node →) update_model_node → END
        Uses the pre-compiled eval_graph built in __init__.
        """
        return self.eval_graph.invoke(state)
