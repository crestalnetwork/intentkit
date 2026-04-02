"""Moralis API client for wallet valuation."""

import logging

import httpx

from intentkit.config.config import config
from intentkit.skills.portfolio.constants import MORALIS_API_BASE_URL

logger = logging.getLogger(__name__)

# Chains to check for wallet net worth
_VALUATION_CHAINS = ["eth", "base", "arbitrum", "bsc"]

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=15)
    return _http_client


async def get_wallet_net_worth(address: str) -> float:
    """Get total USD net worth for a wallet address via Moralis API.

    Checks Ethereum, Base, Arbitrum, and BNB chains.

    Args:
        address: The wallet address to check.

    Returns:
        Total net worth in USD, or 0.0 on any error.
    """
    api_key = config.moralis_api_key
    if not api_key:
        logger.warning("Moralis API key not configured, returning 0.0")
        return 0.0

    url = f"{MORALIS_API_BASE_URL}/wallets/{address}/net-worth"
    headers = {"accept": "application/json", "X-API-Key": api_key}
    params = {
        "exclude_spam": "true",
        "exclude_unverified_contracts": "true",
        "chains": _VALUATION_CHAINS,
    }

    try:
        client = _get_http_client()
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("total_networth_usd", 0.0))
    except Exception as e:
        logger.warning("Failed to get wallet net worth for %s: %s", address, e)
        return 0.0
