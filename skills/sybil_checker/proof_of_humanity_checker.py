import requests
from .base import SybilCheckerSkill

class ProofOfHumanityChecker(SybilCheckerSkill):
    def __init__(self, config):
        self.subgraph_url = "https://api.thegraph.com/subgraphs/name/kleros/proof-of-humanity"

    def check_sybil(self, wallet_address: str) -> dict:
        query = {
            "query": """
            query ($id: ID!) {
                submission(id: $id) {
                    id
                    registered
                    submissionTime
                    name
                }
            }
            """,
            "variables": {
                "id": wallet_address.lower()
            }
        }

        response = requests.post(self.subgraph_url, json=query)
        data = response.json()

        submission = data.get("data", {}).get("submission")
        if submission and submission.get("registered"):
            return {
                "source": "Proof of Humanity",
                "result": {
                    "status": "verified",
                    "details": submission
                }
            }
        else:
            return {
                "source": "Proof of Humanity",
                "result": {
                    "status": "not_verified",
                    "details": None
                }
            }
