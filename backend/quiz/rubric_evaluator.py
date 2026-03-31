"""
RubricEvaluationService — Evaluates student answers against a professor-defined rubric.
This is purely additive and does NOT touch the existing EvaluationService.
"""
import json
import re
from typing import Optional
from .llm_service import llm

#
class RubricEvaluationService:
    """Evaluates a student answer against a structured rubric using the LLM."""

    def evaluate(self, question_text: str, student_answer: str, rubric: dict) -> Optional[dict]:
        """
        Evaluate a student answer against the given rubric.
        
        Args:
            question_text: The question that was asked
            student_answer: The student's answer text
            rubric: Dict with 'total_marks' and 'criteria' list
            
        Returns:
            Dict with criteria_scores, total_awarded, total_max, overall_remark
            or None if evaluation fails
        """
        criteria = rubric.get("criteria", [])
        if not criteria:
            return None

        # Build criteria description for the prompt
        criteria_desc = "\n".join(
            f"  {i+1}. \"{c['name']}\" — {c['marks']} marks"
            for i, c in enumerate(criteria)
        )

        prompt = f"""You are an academic examiner. Evaluate the student's answer against the rubric below.

QUESTION: {question_text}

STUDENT ANSWER: {student_answer}

RUBRIC CRITERIA:
{criteria_desc}

For EACH criterion, decide how many marks to award (0 up to the max for that criterion).
Check for the presence and quality of the keyword/concept described by each criterion.

Respond in EXACTLY this JSON format (no other text):
{{
  "criteria_scores": [
    {{"name": "<criterion name>", "max_marks": <max>, "awarded": <marks given>, "remark": "<1-2 sentence explanation>"}}
  ],
  "overall_remark": "<brief overall assessment>"
}}
"""

        response_text = llm.generate_content(prompt)

        if not response_text or response_text.startswith("ERROR"):
            print(f"[!] RubricEvaluator: LLM returned error: {response_text}")
            return None

        return self._parse_response(response_text, criteria)

    def _parse_response(self, response_text: str, criteria: list) -> Optional[dict]:
        """Parse the LLM JSON response into a structured result."""
        try:
            # Try to extract JSON from the response (handle markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                print(f"[!] RubricEvaluator: No JSON found in response")
                return None

            parsed = json.loads(json_match.group())
            criteria_scores = parsed.get("criteria_scores", [])

            # Calculate totals
            total_awarded = sum(cs.get("awarded", 0) for cs in criteria_scores)
            total_max = sum(c.get("marks", 0) for c in criteria)

            # Clamp awarded marks to not exceed max per criterion
            for cs in criteria_scores:
                max_for_criterion = cs.get("max_marks", 0)
                cs["awarded"] = min(cs.get("awarded", 0), max_for_criterion)
                cs["awarded"] = max(cs["awarded"], 0)  # No negative marks

            # Recalculate after clamping
            total_awarded = sum(cs.get("awarded", 0) for cs in criteria_scores)

            return {
                "criteria_scores": criteria_scores,
                "total_awarded": total_awarded,
                "total_max": total_max,
                "overall_remark": parsed.get("overall_remark", "")
            }

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[!] RubricEvaluator: Failed to parse response: {e}")
            print(f"    Raw response: {response_text[:500]}")
            return None
