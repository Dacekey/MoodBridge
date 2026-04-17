import os
import requests

url = os.getenv("LLM_BASE_URL")
api_key = os.getenv("LLM_API_KEY")
model = os.getenv("LLM_MODEL")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say hello in one short sentence."}
    ],
    "temperature": 0.7,
    "max_tokens": 50,
}

resp = requests.post(url, headers=headers, json=payload, timeout=30)
print("status:", resp.status_code)
print(resp.text)