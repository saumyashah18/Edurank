import sys
import os
sys.path.append(os.getcwd())
from backend.quiz.llm_service import llm
print("Testing DeepSeek via OpenRouter...")
res = llm.generate_content("Hello, this is a test. Reply with 'DeepSeek is active'.")
print(f"Response: {res}")
