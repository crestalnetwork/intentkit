import os
import requests
from dotenv import load_dotenv

load_dotenv()

HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
BASE_URL = "https://api.helius.xyz/v0"

def get_token_holders(mint_address):
    url = f"{BASE_URL}/tokens/{mint_address}/holders?api-key={HELIUS_API_KEY}"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch holders: {response.text}")

    return response.json()

def get_wallet_rank(wallet_address, mint_address):
    holders = get_token_holders(mint_address)

    sorted_holders = sorted(holders, key=lambda x: int(x["amountRaw"]), reverse=True)

    total_holders = len(sorted_holders)
    top_holder = sorted_holders[0]

    wallet_rank = None
    wallet_balance = 0

    for i, holder in enumerate(sorted_holders, start=1):
        if holder["owner"] == wallet_address:
            wallet_rank = i
            wallet_balance = int(holder["amountRaw"]) / (10**9)
            break

    result = {
        "wallet_address": wallet_address,
        "wallet_rank": wallet_rank or "Not a holder",
        "wallet_balance": wallet_balance,
        "top_holder": {
            "address": top_holder["owner"],
            "amount": int(top_holder["amountRaw"]) / (10**9)
        },
        "total_holders": total_holders
    }

    return result
  
