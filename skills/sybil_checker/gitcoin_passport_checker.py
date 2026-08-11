import requests
from .base import SybilCheckerSkill

class GitcoinPassportChecker(SybilCheckerSkill):
    def __init__(self, config):
        self.api_key = config.get("api_key")
        self.base_url = "https://api.scorer.gitcoin.co"

    def check_sybil(self, wallet_address: str) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/v1/score/{wallet_address}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return {
                "source": "Gitcoin Passport",
                "result": response.json()
            }
        else:
            return {
                "source": "Gitcoin Passport",
                "error": f"Failed with status {response.status_code}"
            }
