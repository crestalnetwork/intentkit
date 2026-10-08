from skills.base import Skill

class SybilCheckerSkill(Skill):
    def check_sybil(self, wallet_address: str) -> dict:
        raise NotImplementedError("Must implement check_sybil method")
