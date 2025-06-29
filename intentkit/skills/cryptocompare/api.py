"""CryptoCompare API implementation and shared schemas."""

import time
from typing import List

import httpx
from pydantic import BaseModel, Field

CRYPTO_COMPARE_BASE_URL = "https://min-api.cryptocompare.com"


# Input Schemas
class FetchNewsInput(BaseModel):
    """Input schema for fetching news."""

    token: str = Field(
        ..., description="Token symbol to fetch news for (e.g., BTC, ETH, SOL)"
    )


class FetchPriceInput(BaseModel):
    """Input schema for fetching crypto prices."""

    from_symbol: str = Field(
        ...,
        description="Base cryptocurrency symbol to get prices for (e.g., 'BTC', 'ETH')",
    )
    to_symbols: List[str] = Field(
        ...,
        description="List of target currencies (fiat or crypto) (e.g., ['USD', 'EUR', 'JPY'])",
    )


class FetchTradingSignalsInput(BaseModel):
    """Input schema for fetching trading signals."""

    from_symbol: str = Field(
        ...,
        description="Cryptocurrency symbol to fetch trading signals for (e.g., 'BTC')",
    )


class FetchTopMarketCapInput(BaseModel):
    """Input schema for fetching top cryptocurrencies by market cap."""

    to_symbol: str = Field(
        "USD",
        description="Quote currency for market cap calculation (e.g., 'USD', 'EUR')",
    )


class FetchTopExchangesInput(BaseModel):
    """Input schema for fetching top exchanges for a trading pair."""

    from_symbol: str = Field(
        ..., description="Base cryptocurrency symbol for the trading pair (e.g., 'BTC')"
    )
    to_symbol: str = Field(
        "USD",
        description="Quote currency symbol for the trading pair. Defaults to 'USD'",
    )


class FetchTopVolumeInput(BaseModel):
    """Input schema for fetching top cryptocurrencies by trading volume."""

    to_symbol: str = Field(
        "USD", description="Quote currency for volume calculation. Defaults to 'USD'"
    )


# API Functions
async def fetch_price(api_key: str, from_symbol: str, to_symbols: List[str]) -> dict:
    """
    Fetch current price for a cryptocurrency in multiple currencies.
    """
    url = f"{CRYPTO_COMPARE_BASE_URL}/data/price"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
    params = {"fsym": from_symbol.upper(), "tsyms": ",".join(to_symbols)}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_trading_signals(api_key: str, from_symbol: str) -> dict:
    """
    Fetch the latest trading signals.
    """
    url = f"{CRYPTO_COMPARE_BASE_URL}/data/tradingsignals/intotheblock/latest"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
    params = {"fsym": from_symbol.upper()}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_top_market_cap(
    api_key: str, limit: int, to_symbol: str = "USD"
) -> dict:
    """
    Fetch top cryptocurrencies by market cap.
    """
    url = f"{CRYPTO_COMPARE_BASE_URL}/data/top/mktcapfull"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
    params = {"limit": limit, "tsym": to_symbol.upper()}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_top_exchanges(
    api_key: str, from_symbol: str, to_symbol: str = "USD"
) -> dict:
    """
    Fetch top exchanges for a cryptocurrency pair.
    """
    url = f"{CRYPTO_COMPARE_BASE_URL}/data/top/exchanges"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
    params = {"fsym": from_symbol.upper(), "tsym": to_symbol.upper()}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_top_volume(api_key: str, limit: int, to_symbol: str = "USD") -> dict:
    """
    Fetch top cryptocurrencies by total volume.
    """
    url = f"{CRYPTO_COMPARE_BASE_URL}/data/top/totalvolfull"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
    params = {"limit": limit, "tsym": to_symbol.upper()}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_news(api_key: str, token: str, timestamp: int = None) -> dict:
    """
    Fetch news for a specific token and timestamp.
    """
    if timestamp is None:
        timestamp = int(time.time())
    url = f"{CRYPTO_COMPARE_BASE_URL}/data/v2/news/?lang=EN&lTs={timestamp}&categories={token}&sign=true"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()
