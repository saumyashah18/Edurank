import os
import requests
from dotenv import load_dotenv

def verify_llama():
    load_dotenv()
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    
    print(f"[*] Verifying Llama/Ollama at: {ollama_url}")
    print(f"[*] Base model: {ollama_model}")
    
    # 1. Test Generate
    print("\n[1/2] Testing /api/generate...")
    gen_payload = {
        "model": ollama_model,
        "prompt": "Say 'Ollama is ready' if you can hear me.",
        "stream": False
    }
    try:
        resp = requests.post(f"{ollama_url}/api/generate", json=gen_payload, timeout=30)
        resp.raise_for_status()
        result = resp.json().get("response", "").strip()
        print(f"[+] Response: {result}")
    except Exception as e:
        print(f"[!] Generate failed: {e}")
        
    # 2. Test Embeddings
    print("\n[2/2] Testing /api/embeddings...")
    embed_payload = {
        "model": ollama_model,
        "prompt": "This is a test sentence for embeddings."
    }
    try:
        resp = requests.post(f"{ollama_url}/api/embeddings", json=embed_payload, timeout=30)
        resp.raise_for_status()
        embedding = resp.json().get("embedding", [])
        print(f"[+] Embedding dimension: {len(embedding)}")
        if len(embedding) == 4096:
            print("[+] Dimension matches Llama3.1 (4096).")
        else:
            print(f"[?] Unexpected dimension: {len(embedding)}")
    except Exception as e:
        print(f"[!] Embeddings failed: {e}")

if __name__ == "__main__":
    verify_llama()
