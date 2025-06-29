"""API interface for wallet data providers (EVM chains and Solana)."""

import logging
from typing import Dict

import httpx

from intentkit.skills.moralis.base import CHAIN_MAPPING

logger = logging.getLogger(__name__)

#############################################
# EVM Chains API (Ethereum, BSC, etc.)
#############################################


async def fetch_moralis_data(
    api_key: str, endpoint: str, address: str, chain_id: int = None, params: dict = None
) -> dict:
    """Base function for Moralis API calls.

    Args:
        api_key: Moralis API key
        endpoint: API endpoint (with {address} placeholder if needed)
        address: Wallet address to query
        chain_id: Blockchain network ID
        params: Additional query parameters

    Returns:
        Response data from the API or error
    """

    if not api_key:
        logger.error("API key not configured")
        return {"error": "API key not configured"}

    base_url = "https://deep-index.moralis.io/api/v2.2"
    headers = {"X-API-Key": api_key}

    url = f"{base_url}/{endpoint.format(address=address)}"

    if chain_id:
        params = params or {}
        params["chain"] = CHAIN_MAPPING.get(chain_id, "eth")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"API request error: {e}")
            return {"error": str(e)}
        except httpx.HTTPStatusError as e:
            logger.error(f"API error: {e.response.status_code} {e.response.text}")
            return {"error": f"HTTP error {e.response.status_code}"}


# Wallet Balances
async def fetch_wallet_balances(
    api_key: str, address: str, chain_id: int = None
) -> dict:
    """Get token balances with prices.

    Args:
        api_key: API key for the data provider
        address: Wallet address to query
        chain_id: Blockchain network ID

    Returns:
        Token balances with additional data
    """
    endpoint = "wallets/{address}/tokens"
    return await fetch_moralis_data(api_key, endpoint, address, chain_id)


# NFT Balances
async def fetch_nft_data(
    api_key: str, address: str, chain_id: int = None, params: dict = None
) -> dict:
    """Get NFT balances.

    Args:
        api_key: API key for the data provider
        address: Wallet address to query
        chain_id: Blockchain network ID
        params: Additional query parameters

    Returns:
        NFT data including metadata
    """
    endpoint = "{address}/nft"
    default_params = {"normalizeMetadata": True}
    if params:
        default_params.update(params)
    return await fetch_moralis_data(
        api_key, endpoint, address, chain_id, default_params
    )


# Transaction History
async def fetch_transaction_history(
    api_key: str,
    address: str,
    chain_id: int = None,
    cursor: str = None,
    limit: int = 100,
) -> dict:
    """Get wallet transaction history.

    Args:
        api_key: API key for the data provider
        address: Wallet address to query
        chain_id: Blockchain network ID
        cursor: Pagination cursor
        limit: Maximum number of transactions to return

    Returns:
        Transaction history data
    """
    endpoint = "wallets/{address}/history"
    params = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    return await fetch_moralis_data(api_key, endpoint, address, chain_id, params)


# Token Approvals
async def fetch_token_approvals(
    api_key: str, address: str, chain_id: int = None
) -> dict:
    """Get token approvals.

    Args:
        api_key: API key for the data provider
        address: Wallet address to query
        chain_id: Blockchain network ID

    Returns:
        Token approval data
    """
    endpoint = "wallets/{address}/approvals"
    return await fetch_moralis_data(api_key, endpoint, address, chain_id)


# Net Worth
async def fetch_net_worth(api_key: str, address: str) -> dict:
    """Get wallet net worth.

    Args:
        api_key: API key for the data provider
        address: Wallet address to query

    Returns:
        Net worth data across all chains
    """
    endpoint = "wallets/{address}/net-worth"
    return await fetch_moralis_data(api_key, endpoint, address)


#############################################
# Solana API
#############################################


async def fetch_solana_api(api_key: str, endpoint: str, params: Dict = None) -> Dict:
    """Base function for Solana API calls using Moralis.

    Args:
        api_key: API key for the data provider
        endpoint: API endpoint
        params: Additional query parameters

    Returns:
        Response data from the API or error
    """

    if not api_key:
        logger.error("API key not configured")
        return {"error": "API key not configured"}

    base_url = "https://solana-gateway.moralis.io"
    headers = {"X-API-Key": api_key}
    url = f"{base_url}{endpoint}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Solana API request error: {e}")
            return {"error": str(e)}
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Solana API error: {e.response.status_code} {e.response.text}"
            )
            return {"error": f"HTTP error {e.response.status_code}: {e.response.text}"}


async def get_solana_portfolio(
    api_key: str, address: str, network: str = "mainnet"
) -> Dict:
    """Get complete portfolio for a Solana wallet.

    Args:
        api_key: API key for the data provider
        address: Solana wallet address
        network: Solana network (mainnet or devnet)

    Returns:
        Complete portfolio including SOL and SPL tokens
    """
    endpoint = f"/account/{network}/{address}/portfolio"
    return await fetch_solana_api(api_key, endpoint)


async def get_solana_balance(
    api_key: str, address: str, network: str = "mainnet"
) -> Dict:
    """Get native SOL balance.

    Args:
        api_key: API key for the data provider
        address: Solana wallet address
        network: Solana network (mainnet or devnet)

    Returns:
        Native SOL balance
    """
    endpoint = f"/account/{network}/{address}/balance"
    return await fetch_solana_api(api_key, endpoint)


async def get_solana_spl_tokens(
    api_key: str, address: str, network: str = "mainnet"
) -> Dict:
    """Get SPL token balances.

    Args:
        api_key: API key for the data provider
        address: Solana wallet address
        network: Solana network (mainnet or devnet)

    Returns:
        SPL token balances
    """
    endpoint = f"/account/{network}/{address}/tokens"
    return await fetch_solana_api(api_key, endpoint)


async def get_solana_nfts(api_key: str, address: str, network: str = "mainnet") -> Dict:
    """Get NFTs owned by a Solana wallet.

    Args:
        api_key: API key for the data provider
        address: Solana wallet address
        network: Solana network (mainnet or devnet)

    Returns:
        NFT holdings
    """
    endpoint = f"/account/{network}/{address}/nft"
    return await fetch_solana_api(api_key, endpoint)


async def get_token_price(
    api_key: str, token_address: str, network: str = "mainnet"
) -> Dict:
    """Get token price by mint address.

    Args:
        api_key: API key for the data provider
        token_address: Token mint address
        network: Solana network (mainnet or devnet)

    Returns:
        Token price data
    """
    endpoint = f"/token/{network}/{token_address}/price"
    return await fetch_solana_api(api_key, endpoint)
