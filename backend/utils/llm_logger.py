import time
import json
from typing import List, Dict, Any, Optional, Union
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
        response: Any,
        latency_ms: float,
        extra: dict = None    # optional — e.g. {"chunk_id": 42, "score": 0.7}
    ):
        is_error = isinstance(response, str) and response.startswith("ERROR")
        record = {
            "ts": datetime.utcnow().isoformat(),
            "caller": caller,
            "prompt_chars": len(prompt) if isinstance(prompt, str) else 0,
            "response_chars": len(response) if isinstance(response, (str, list)) else 0,
            "latency_ms": round(latency_ms, 1),
            "success": not is_error,
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
