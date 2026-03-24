import os
import requests
from dotenv import load_dotenv

load_dotenv()

"""
EduRank LLM Service Configuration (.env)

LLM_MODE=local                          # "local" or "api", default "local"

# Local Ollama config
OLLAMA_URL=http://localhost:11434        # default
OLLAMA_MODEL=llama3.1:8b                # default

# API config (OpenRouter or any OpenAI-compatible endpoint)
OPENROUTER_API_KEY=                     # required if LLM_MODE=api
OPENROUTER_URL=https://openrouter.ai/api/v1/chat/completions
OPENROUTER_MODEL=mistralai/mixtral-8x7b-instruct
"""

class LLMService:
    def __init__(self):
        self.mode = os.getenv("LLM_MODE", "local").lower()
        
        # Ollama config
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        
        # API config
        self.api_url = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_model = os.getenv("OPENROUTER_MODEL", "mistralai/mixtral-8x7b-instruct")
        
        print(f"[LLMService] Mode: {self.mode} | Model: {self.model_name}")

    @property
    def model_name(self) -> str:
        """Returns the active model name for logging."""
        return self.ollama_model if self.mode == "local" else self.api_model

    def generate_content(self, prompt: str, system_prompt: str = None) -> str:
        """Routes to local or API provider based on mode."""
        if self.mode == "local":
            return self._call_ollama(prompt, system_prompt)
        else:
            return self._call_openrouter(prompt, system_prompt)

    def _call_ollama(self, prompt: str, system_prompt: str = None) -> str:
        """Calls local Ollama instance via REST."""
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 1024
            }
        }
        try:
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            return "ERROR: Ollama is not running. Run 'ollama serve' first."
        except requests.exceptions.Timeout:
            return "ERROR: Ollama timed out. Model may still be loading."
        except Exception as e:
            return f"ERROR: {e}"

    def _call_openrouter(self, prompt: str, system_prompt: str = None) -> str:
        """Calls OpenRouter or any OpenAI-compatible API."""
        if not self.api_key:
            return "ERROR: OPENROUTER_API_KEY not set in .env"
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "EduRank"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.api_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            if response.status_code == 429:
                return "ERROR_RATE_LIMIT"
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"ERROR: {e}"

    def validate(self) -> bool:
        """
        Sends a minimal test prompt to verify the LLM is reachable.
        Returns True if reachable, False if not.
        """
        test_response = self.generate_content("Reply with the word OK and nothing else.")
        success = "ERROR" not in test_response
        status = "REACHABLE" if success else "UNREACHABLE"
        print(f"[LLMService] Validation: {status} | Response: {test_response[:80]}")
        return success

# Global instance
llm = LLMService()
