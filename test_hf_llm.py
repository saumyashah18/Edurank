from backend.quiz.llm_service import llm
import sys

print("Testing Hugging Face Integration...")
print(f"Model: {llm.model_name}")
print(f"Using Hugging Face: {getattr(llm, 'use_hf', False)}")

if not getattr(llm, 'use_hf', False):
    print("❌ Error: Service is NOT using Hugging Face.")
    sys.exit(1)

try:
    print("Sending request to Qwen 2.5...")
    response = llm.generate_content("What is the capital of France? Answer in one word.")
    print(f"Response: {response}")
    
    if "Paris" in response or "paris" in response:
        print("✅ Success: Model responded correctly.")
    else:
        print("⚠️ Warning: Model responded, but answer may be unexpected.")
except Exception as e:
    print(f"❌ Error during generation: {e}")
