import requests
import os

class DeepSeekR1Backend:
    """
    DeepSeek R1 backend for IntentKit.
    Provides high-performance reasoning and function calling capabilities.
    """
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/v1/chat/completions"

    def call(self, messages, tools=None):
        payload = {
            "model": "deepseek-reasoner",
            "messages": messages,
            "tools": tools,
            "stream": False
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        response = requests.post(self.base_url, headers=headers, json=payload)
        return response.json()
