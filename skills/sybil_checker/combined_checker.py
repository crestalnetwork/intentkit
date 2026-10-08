from .base import SybilCheckerSkill
from .gitcoin_passport_checker import GitcoinPassportChecker
from .proof_of_humanity_checker import ProofOfHumanityChecker

class CombinedSybilChecker(SybilCheckerSkill):
    def __init__(self, config):
        self.gitcoin_checker = GitcoinPassportChecker(config)
        self.poh_checker = ProofOfHumanityChecker(config)

    def check_sybil(self, wallet_address: str) -> dict:
        gitcoin_result = self.gitcoin_checker.check_sybil(wallet_address)
        poh_result = self.poh_checker.check_sybil(wallet_address)

        return {
            "wallet": wallet_address,
            "results": [
                gitcoin_result,
                poh_result
            ]
        }
