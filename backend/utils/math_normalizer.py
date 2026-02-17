import re
from typing import Dict, List, Tuple


class MathNormalizer:
    """
    Converts spoken mathematical expressions to symbolic notation.
    
    Examples:
        "a is equal to b plus c" → "a = b + c"
        "x squared minus y" → "x² - y"
        "two times three" → "2 × 3"
    """
    
    def __init__(self):
        # Basic operators
        self.operator_replacements = {
            r'\bis equal to\b': '=',
            r'\bequals\b': '=',
            r'\bequal\b': '=',
            r'\bplus\b': '+',
            r'\bminus\b': '-',
            r'\btimes\b': '×',
            r'\bmultiplied by\b': '×',
            r'\bdivided by\b': '÷',
            r'\bover\b': '/',
            r'\bmod\b': '%',
            r'\bmodulo\b': '%',
        }
        
        # Comparison operators
        self.comparison_replacements = {
            r'\bgreater than or equal to\b': '≥',
            r'\bless than or equal to\b': '≤',
            r'\bgreater than\b': '>',
            r'\bless than\b': '<',
            r'\bnot equal to\b': '≠',
        }
        
        # Powers and roots
        self.power_replacements = {
            r'\bsquared\b': '²',
            r'\bcubed\b': '³',
            r'\bto the power of (\w+)\b': r'^\1',
            r'\bto the (\w+) power\b': r'^\1',
            r'\bsquare root of\b': '√',
            r'\bsqrt of\b': '√',
        }
        
        # Greek letters (common in math)
        self.greek_replacements = {
            r'\balpha\b': 'α',
            r'\bbeta\b': 'β',
            r'\bgamma\b': 'γ',
            r'\bdelta\b': 'δ',
            r'\bepsilon\b': 'ε',
            r'\btheta\b': 'θ',
            r'\blambda\b': 'λ',
            r'\bmu\b': 'μ',
            r'\bpi\b': 'π',
            r'\bsigma\b': 'σ',
            r'\bomega\b': 'ω',
        }
        
        # Number words to digits
        self.number_words = {
            r'\bzero\b': '0',
            r'\bone\b': '1',
            r'\btwo\b': '2',
            r'\bthree\b': '3',
            r'\bfour\b': '4',
            r'\bfive\b': '5',
            r'\bsix\b': '6',
            r'\bseven\b': '7',
            r'\beight\b': '8',
            r'\bnine\b': '9',
            r'\bten\b': '10',
        }
        
        # Special functions
        self.function_replacements = {
            r'\bsine of\b': 'sin',
            r'\bsin of\b': 'sin',
            r'\bcosine of\b': 'cos',
            r'\bcos of\b': 'cos',
            r'\btangent of\b': 'tan',
            r'\btan of\b': 'tan',
            r'\blog of\b': 'log',
            r'\bnatural log of\b': 'ln',
            r'\bln of\b': 'ln',
        }
    
    def normalize(self, text: str) -> str:
        """
        Convert spoken mathematical expression to symbolic notation.
        
        Args:
            text: Spoken mathematical expression
            
        Returns:
            Normalized mathematical expression with symbols
        """
        if not text or not text.strip():
            return text
        
        result = text.lower().strip()
        
        # Apply replacements in order of specificity (most specific first)
        replacement_groups = [
            self.comparison_replacements,  # "greater than or equal to" before "greater than"
            self.power_replacements,
            self.function_replacements,
            self.greek_replacements,
            self.operator_replacements,
            self.number_words,
        ]
        
        for replacements in replacement_groups:
            for pattern, replacement in replacements.items():
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        # Clean up spacing around operators
        result = self._clean_spacing(result)
        
        return result
    
    def _clean_spacing(self, text: str) -> str:
        """Remove extra spaces around mathematical operators."""
        # Add space around operators for readability
        operators = ['=', '+', '-', '×', '÷', '/', '>', '<', '≥', '≤', '≠', '%']
        
        for op in operators:
            # Remove existing spaces
            text = re.sub(rf'\s*{re.escape(op)}\s*', op, text)
            # Add single space on both sides
            text = text.replace(op, f' {op} ')
        
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Remove spaces before/after parentheses
        text = re.sub(r'\s*\(\s*', '(', text)
        text = re.sub(r'\s*\)\s*', ')', text)
        
        # Remove spaces before superscripts (², ³, etc.)
        text = re.sub(r'\s+([²³⁴⁵⁶⁷⁸⁹⁰¹])', r'\1', text)
        
        # Remove spaces after square root and before the operand
        text = re.sub(r'√\s+', '√', text)
        
        return text.strip()
    
    def contains_math(self, text: str) -> bool:
        """
        Check if text likely contains mathematical expressions.
        
        Returns:
            True if text contains math-related keywords
        """
        math_keywords = [
            'equal', 'plus', 'minus', 'times', 'divided',
            'squared', 'cubed', 'power', 'root',
            'greater', 'less', 'than',
            'sin', 'cos', 'tan', 'log',
            'alpha', 'beta', 'gamma', 'theta', 'pi'
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in math_keywords)


# Global instance for easy import
math_normalizer = MathNormalizer()


# Convenience function
def normalize_math_speech(text: str) -> str:
    """
    Convenience function to normalize mathematical speech.
    
    Args:
        text: Spoken mathematical expression
        
    Returns:
        Normalized expression with symbols
        
    Example:
        >>> normalize_math_speech("a is equal to b plus c")
        'a = b + c'
    """
    return math_normalizer.normalize(text)
