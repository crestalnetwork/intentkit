# check_balance.py
import requests
from .base import MultichainBaseTool

class CheckBalance(MultichainBaseTool):
    def run(self, api_key: str, wallet_address: str) -> str:
        chains = {
            "Ethereum": 1,
            "Polygon": 137,
            "BNB Chain": 56,
            "Arbitrum": 42161,
            "Optimism": 10
        }

        grand_total = 0
        result = ""

        for name, chain_id in chains.items():
            result += f"\n========== {name} ==========\n"
            url = f"https://api.covalenthq.com/v1/{chain_id}/address/{wallet_address}/balances_v2/?key={api_key}"
            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                result += f"Error fetching data for {name}: {e}\n"
                continue

            tokens = data.get("data", {}).get("items", [])
            total_chain = 0

            for token in tokens:
                balance = int(token.get("balance", 0)) / (10 ** token.get("contract_decimals", 18))
                value = token.get("quote", 0)
                symbol = token.get("contract_ticker_symbol", "N/A")
                if value and value > 0:
                    result += f"{symbol}: {balance:.4f} ≈ ${value:,.2f}\n"
                    total_chain += value

            result += f"Total on {name}: ${total_chain:,.2f}\n"
            grand_total += total_chain

        result += "\n==============================\n"
        result += f"GRAND TOTAL VALUE ACROSS CHAINS: ${grand_total:,.2f}\n"

        return result
