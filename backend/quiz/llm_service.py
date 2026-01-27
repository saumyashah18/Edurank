import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("LLM_MODEL", "google/gemini-2.5-flash")
        
        # OpenRouter uses the OpenAI client format
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )

    def generate_content(self, prompt: str, system_prompt: str = None) -> str:
        """Generates text content using OpenRouter (Gemini 2.5 Flash) with optional system instruction."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            return completion.choices[0].message.content
        except Exception as e:
            print(f"OpenRouter LLM Error: {e}")
            import traceback
            traceback.print_exc()
            return f"Error: {e}"

# Global instance
llm = LLMService()
