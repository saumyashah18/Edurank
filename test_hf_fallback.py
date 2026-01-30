import os
import traceback
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("HF_TOKEN")
model = "sentence-transformers/all-MiniLM-L6-v2"

client = InferenceClient(model=model, token=token)

print(f"Testing embedding for model: {model}")
try:
    emb = client.feature_extraction("Hello world")
    print(f"Success! Embedding length: {len(emb)}")
except Exception as e:
    print(f"Caught Exception: {type(e).__name__}: {e}")
    traceback.print_exc()
