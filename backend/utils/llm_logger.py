import time
import json
from datetime import datetime

class LLMCallLogger:
    """
    Wraps any LLM call with structured logging.
    Logs: timestamp, caller, prompt_chars, response_chars,
          latency_ms, success, error (if any).
    Output goes to stdout as a single JSON line per call.
    """

    @staticmethod
    def log_call(
        caller: str,          # e.g. "EvaluationService", "ProfessorBot", "ConceptExtractor"
        prompt: str,
        response: str,
        latency_ms: float,
        extra: dict = None    # optional — e.g. {"chunk_id": 42, "score": 0.7}
    ):
        record = {
            "ts": datetime.utcnow().isoformat(),
            "caller": caller,
            "prompt_chars": len(prompt),
            "response_chars": len(response) if response else 0,
            "latency_ms": round(latency_ms, 1),
            "success": not (response or "").startswith("ERROR"),
        }
        if extra:
            record.update(extra)
        print(f"[LLM_LOG] {json.dumps(record)}")

    @staticmethod
    def timed_call(caller: str, prompt: str, llm_fn, extra: dict = None) -> str:
        """
        Wraps an LLM call with timing and logging.
        Usage:
            response = LLMCallLogger.timed_call(
                caller="ProfessorBot",
                prompt=user_prompt,
                llm_fn=lambda: llm.generate_content(user_prompt, system_prompt=system_prompt),
                extra={"chunk_id": chunk.id, "turn": turn_number}
            )
        Returns the raw response string.
        """
        start = time.time()
        try:
            response = llm_fn()
        except Exception as e:
            response = f"ERROR: {e}"
        latency_ms = (time.time() - start) * 1000
        LLMCallLogger.log_call(caller, prompt, response, latency_ms, extra)
        return response
