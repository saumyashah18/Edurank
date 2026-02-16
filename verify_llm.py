import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from quiz.llm_service import llm

def test_generation():
    print(f"Testing generation with model: {llm.model_name}")
    try:
        response = llm.generate_content("Hello, introduce yourself briefly.")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_generation()
