from backend.quiz.llm_service import llm
import os

def test_llm():
    print(f"[*] Testing LLM: {os.getenv('LLM_MODEL')}")
    prompt = "Generate a high-level academic question about James Scott's 'Seeing like a State'. Format: Question: [text] Ideal Answer: [text]"
    system_prompt = "You are an expert academic examiner."
    
    response = llm.generate_content(prompt, system_prompt=system_prompt)
    print("\n--- RAW RESPONSE ---")
    print(response)
    print("\n--- END RESPONSE ---")

if __name__ == "__main__":
    test_llm()
