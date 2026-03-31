import re
import json
import os
from typing import List, Dict, Any
#
class MathNormalizer:
    """
    Converts spoken mathematical expressions to symbolic notation using a shared rule set.
    """
    
    def __init__(self):
        self.rules = []
        self._load_rules()

    def _load_rules(self):
        """Load normalization rules from the shared JSON file."""
        # The shared directory is at the project root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        rules_path = os.path.join(base_dir, "shared", "math_rules.json")
        
        try:
            if os.path.exists(rules_path):
                with open(rules_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.rules = data.get("rules", [])
            else:
                print(f"[MathNormalizer] Warning: rules file not found at {rules_path}")
        except Exception as e:
            print(f"[MathNormalizer] Error loading math rules: {e}")

    def normalize(self, text: str) -> str:
        """
        Convert spoken mathematical expression to symbolic notation.
        """
        if not text:
            return ""
        
        result = text.lower().strip()
        
        for rule in self.rules:
            symbol = rule.get("symbol")
            position = rule.get("position", "infix")
            is_regex = rule.get("regex", False)
            
            # Sort spoken triggers by length descending to match longest first
            # (e.g., "is equal to" before "equal to")
            spoken_triggers = rule.get("spoken", [])
            if not is_regex:
                spoken_triggers = sorted(spoken_triggers, key=len, reverse=True)
            
            for spoken in spoken_triggers:
                if is_regex:
                    # Use the spoken string directly as a regex pattern
                    pattern = spoken
                    # Replace $1 with the first capture group \1
                    replacement = symbol.replace("$1", r"\1")
                    result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
                elif position == "postfix":
                    # e.g., "x squared" -> "x²"
                    result = re.sub(rf"(\w+)\s+{re.escape(spoken)}\b", rf"\1{symbol}", result, flags=re.IGNORECASE)
                elif position == "prefix":
                    # e.g., "square root of x" -> "√x"
                    result = re.sub(rf"\b{re.escape(spoken)}\s+(\w+)", rf"{symbol}\1", result, flags=re.IGNORECASE)
                else:
                    # infix or simple substitution (e.g., "pi" -> "π")
                    result = re.sub(rf"\b{re.escape(spoken)}\b", symbol, result, flags=re.IGNORECASE)

        return self._clean_spacing(result)

    def _clean_spacing(self, text: str) -> str:
        """Clean up mathematical notation spacing for readability."""
        # Operators that should have spaces around them
        infix_ops = ['=', '+', '−', '×', '/', '>', '<', '≥', '≤', '≈', '≠', '∴']
        for op in infix_ops:
            text = re.sub(rf"\s*{re.escape(op)}\s*", f" {op} ", text)
        
        # Remove extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Specific cleanup for units/symbols that shouldn't have preceding space
        # e.g., "x ²" -> "x²"
        text = re.sub(r'\s+([²³^])', r'\1', text)
        
        # Prefix symbols shouldn't have FOLLOWING space
        # e.g., "√ x" -> "√x"
        text = re.sub(r'([√])\s+', r'\1', text)
        
        return text

    def contains_math(self, text: str) -> bool:
        """Heuristic to check if text contains math-related keywords."""
        if not text: return False
        text_lower = text.lower()
        # Extract all possible spoken triggers from rules
        triggers = []
        for r in self.rules:
            triggers.extend(r.get("spoken", []))
        
        return any(re.search(rf"\b{re.escape(t)}\b", text_lower) for t in triggers)

# Global instance
math_normalizer = MathNormalizer()

def normalize_math_speech(text: str) -> str:
    """Convenience function to access the global normalizer instance."""
    return math_normalizer.normalize(text)
