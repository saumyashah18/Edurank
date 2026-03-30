import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_huggingface():
    token = os.getenv("HF_TOKEN")
    url = os.getenv("HUGGINGFACE_URL", "https://router.huggingface.co/v1/chat/completions")
    model = os.getenv("HUGGINGFACE_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    
    print(f"[*] Testing Hugging Face API...")
    print(f"[*] URL: {url}")
    print(f"[*] Model: {model}")
    print(f"[*] Token: {token[:5]}...{token[-5:] if token else 'None'}")
    
    if not token:
        print("[!] Error: HF_TOKEN not found in .env")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Extract concepts from this: Photosynthesis is the process by which plants use sunlight to synthesize nutrients from carbon dioxide and water. Respond in JSON format: {'concepts': [{'name': '...', 'description': '...'}]}"}
        ],
        "max_tokens": 500
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"[*] Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"[!] Error Response: {response.text}")
            return
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print(f"\n[+] HF Extraction Result:\n{content}")
    except Exception as e:
        print(f"[!] Request failed: {e}")

if __name__ == "__main__":
    test_huggingface()
