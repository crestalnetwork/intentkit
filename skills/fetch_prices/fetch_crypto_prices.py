import requests

def run(token_name: str = "bitcoin") -> dict:
    """
    Fetch the current price and market data for a cryptocurrency using CoinGecko API.

    Args:
        token_name (str): The name of the cryptocurrency (e.g., 'bitcoin', 'ethereum').

    Returns:
        dict: A dictionary with price, market cap, and 24h change.
    """
    url = f"https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": token_name.lower(),
        "vs_currencies": "usd",
        "include_market_cap": "true",
        "include_24hr_change": "true"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if token_name not in data:
            return {"error": f"Token '{token_name}' not found on CoinGecko."}

        token_data = data[token_name]
        return {
            "token": token_name,
            "price_usd": token_data["usd"],
            "market_cap_usd": token_data.get("usd_market_cap"),
            "24h_change_percent": round(token_data.get("usd_24h_change", 0), 2)
        }

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
