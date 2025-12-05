import requests

url = "http://localhost:4891/v1/chat/completions"  # adjust if needed

payload = {
    "model": "Llama 3.2 3B Instruct",  # exact name from GPT4All
    "messages": [
        {"role": "user", "content": "Say in one sentence what a credit analyst does."}
    ],
    "max_tokens": 50,
}

print(f"Sending test request to {url} ...")
r = requests.post(url, json=payload, timeout=60)
print("Status:", r.status_code)
print("Response:", r.text)
