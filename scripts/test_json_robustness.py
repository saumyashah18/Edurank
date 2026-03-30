import json
import re
from typing import Optional

def _extract_json(text: str) -> Optional[dict]:
    """Robustly extracts JSON from a string, handling markdown blocks and preambles."""
    clean = text.strip()
    
    # 1. Try direct parse
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
        
    # 2. Try stripping markdown fences
    if "```" in clean:
        # Matches ```json ... ``` or just ``` ... ```
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

    # 3. Last resort: Find the first { and last }
    start = clean.find('{')
    end = clean.rfind('}')
    if start != -1 and end != -1:
        try:
            return json.loads(clean[start:end+1])
        except json.JSONDecodeError:
            pass
            
    return None

def test_robust_json():
    test_cases = [
        '{"concepts": [{"name": "test"}]}',
        'Here is your JSON: ```json\n{"concepts": [{"name": "test"}]}\n``` Hope this helps!',
        'No problem! ```\n{"concepts": [{"name": "test"}]}\n```',
        'Direct text preamble {"concepts": [{"name": "test"}]} with postamble'
    ]
    
    for i, case in enumerate(test_cases):
        result = _extract_json(case)
        print(f"Test Case {i+1}: {'SUCCESS' if result and result['concepts'][0]['name'] == 'test' else 'FAILED'}")
        if not result:
            print(f"  Result was None for: {case[:50]}...")

if __name__ == "__main__":
    test_robust_json()
