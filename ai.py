import requests
import os

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-1.5-flash-latest"

def ask_ai(text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

    payload = {
        "contents": [
            {"parts": [{"text": text}]}
        ]
    }

    r = requests.post(url, json=payload)
    data = r.json()

    return data["candidates"][0]["content"]["parts"][0]["text"]
