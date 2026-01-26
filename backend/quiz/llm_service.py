import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=self.api_key)
        # Using gemini-2.0-flash for fast, efficient chat responsiveness
        self.model = genai.GenerativeModel("gemini-2.0-flash")

    def generate_content(self, prompt: str, system_prompt: str = None) -> str:
        """Generates text content using Google Gemini with optional system instruction."""
        try:
            # Note: For Gemini, we can pass system_instruction during model init, 
            # but for per-call flexibility we'll use a combined prompt if needed
            # or re-init the model if system_prompt changes significantly.
            # Here we follow the existing pattern using a simple content generation call.
            
            if system_prompt:
                print(f"[LLM DEBUG] Using System Instruction: {system_prompt[:100]}...")
                # Re-configure with system instruction for the best prompt adherence
                model = genai.GenerativeModel(
                    "gemini-2.0-flash",
                    system_instruction=system_prompt
                )
            else:
                model = self.model
                
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=500,
                    temperature=0.7
                )
            )
            return response.text
        except Exception as e:
            print(f"Gemini LLM Error: {e}")
            return f"Error: {e}"

# Global instance
llm = LLMService()
