import os
from openai import OpenAI
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.hf_api_key = os.getenv("HUGGINGFACE_API_KEY")
        self.model_name = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-72B-Instruct")
        
        # Initialize Google if key is present and model is gemini
        self.use_google = False
        self.use_hf = False
        
        if self.google_api_key and "gemini" in self.model_name.lower():
            genai.configure(api_key=self.google_api_key)
            # Remove "google/" prefix for direct Google API calls if present
            clean_model_name = self.model_name.replace("google/", "")
            self.google_model = genai.GenerativeModel(clean_model_name)
            self.use_google = True
            print(f"[*] LLMService: Using Direct Google API for model {clean_model_name}")
        elif self.hf_api_key:
            from huggingface_hub import InferenceClient
            self.hf_client = InferenceClient(api_key=self.hf_api_key)
            self.use_hf = True
            print(f"[*] LLMService: Using Hugging Face Inference API for model {self.model_name}")
        else:
            # Fallback/Primary OpenRouter
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_api_key,
            )
            print(f"[*] LLMService: Using OpenRouter API for model {self.model_name}")

    def generate_content(self, prompt: str, system_prompt: str = None) -> str:
        """Generates text content using Google, Hugging Face, or OpenRouter."""
        try:
            if self.use_google:
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                response = self.google_model.generate_content(full_prompt)
                
                # Safety check: response.text might raise if blocked
                try:
                    if response and response.text:
                        return response.text
                    return "ERROR: Empty response from AI."
                except (AttributeError, ValueError) as e:
                    print(f"[*] Google AI Blocked/Empty Response: {e}")
                    return "ERROR: The AI was unable to generate a response for this topic."
            elif self.use_hf:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = ""
                try:
                    stream = self.hf_client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        max_tokens=2000,
                        stream=True
                    )
                    for chunk in stream:
                        if chunk.choices and len(chunk.choices) > 0:
                            content = chunk.choices[0].delta.content
                            if content:
                                response += content
                    return response
                except Exception as e:
                    print(f"HF Error details: {e}")
                    return f"ERROR: Hugging Face generation failed: {e}"
            else:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=4000,
                    temperature=0.7
                )
                if not completion or not completion.choices:
                    return "ERROR: No response from OpenRouter."
                return completion.choices[0].message.content
        except (Exception, StopIteration) as e:
            # Prevent StopIteration leaking in generators/coroutines or unexpected HuggingFace/AI library behaviors
            error_str = str(e)
            print(f"LLM Error during generation: {error_str}")
            if "429" in error_str or "rate_limit" in error_str.lower():
                return "ERROR_RATE_LIMIT"
            return f"ERROR: AI generation failed. Details: {error_str[:100]}"

# Global instance
llm = LLMService()
