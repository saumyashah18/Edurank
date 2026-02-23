import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.model_name = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        
        if self.groq_api_key:
            # Groq uses OpenAI-compatible API
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.groq_api_key,
            )
            self.provider = "groq"
            print(f"[*] LLMService: Using Groq API for model {self.model_name}")
        elif self.google_api_key and "gemini" in self.model_name.lower():
            import google.generativeai as genai
            genai.configure(api_key=self.google_api_key)
            clean_model_name = self.model_name.replace("google/", "")
            self.google_model = genai.GenerativeModel(clean_model_name)
            self.provider = "google"
            print(f"[*] LLMService: Using Direct Google API for model {clean_model_name}")
        elif self.openrouter_api_key:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_api_key,
            )
            self.provider = "openrouter"
            print(f"[*] LLMService: Using OpenRouter API for model {self.model_name}")
        else:
            print("[!] LLMService: No API key found! Set GROQ_API_KEY, GOOGLE_API_KEY, or OPENROUTER_API_KEY")
            self.provider = None

    def generate_content(self, prompt: str, system_prompt: str = None) -> str:
        """Generates text content using Groq, Google, or OpenRouter."""
        try:
            if self.provider == "google":
                # Official system_instruction support for modern Gemini models
                if system_prompt:
                    import google.generativeai as genai
                    clean_model_name = self.model_name.replace("google/", "")
                    model = genai.GenerativeModel(
                        model_name=clean_model_name,
                        system_instruction=system_prompt
                    )
                    response = model.generate_content(prompt)
                else:
                    response = self.google_model.generate_content(prompt)

                try:
                    if response and response.text:
                        return response.text
                    return "ERROR: Empty response from AI."
                except (AttributeError, ValueError) as e:
                    print(f"[*] Google AI Blocked/Empty Response: {e}")
                    return "ERROR: The AI was unable to generate a response for this topic."
            
            elif self.provider in ("groq", "openrouter"):
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=2000,
                    temperature=0.7
                )
                if not completion or not completion.choices:
                    return "ERROR: No response from AI."
                return completion.choices[0].message.content
            else:
                return "ERROR: No LLM provider configured."
                
        except (Exception, StopIteration) as e:
            error_str = str(e)
            print(f"LLM Error during generation: {error_str}")
            if "429" in error_str or "rate_limit" in error_str.lower():
                return "ERROR_RATE_LIMIT"
            return f"ERROR: AI generation failed. Details: {error_str[:100]}"

# Global instance
llm = LLMService()
