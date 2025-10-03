import requests

def run(token_name: str = "bitcoin") -> dict:
    """
    Fetch real-time price data for a cryptocurrency from the CoinGecko API.

    Args:
        token_name (str): The cryptocurrency ID (e.g., 'bitcoin', 'ethereum').

    Returns:
        dict: Dictionary containing token name, USD price, market cap, and 24h change.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{token_name.lower()}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        return {
            "token": token_name.lower(),
            "price_usd": data["market_data"]["current_price"]["usd"],
            "market_cap_usd": data["market_data"]["market_cap"]["usd"],
            "24h_change_percent": data["market_data"]["price_change_percentage_24h"]
        }

    except requests.RequestException as e:
        return {"error": f"Failed to fetch data: {str(e)}"}
    except KeyError:
        return {"error": "Unexpected response format. Please check token name."}
