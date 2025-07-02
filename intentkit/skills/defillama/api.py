"""DeFi Llama API implementation and shared schemas."""

from datetime import datetime
from typing import List, Optional

import httpx

DEFILLAMA_TVL_BASE_URL = "https://api.llama.fi"
DEFILLAMA_COINS_BASE_URL = "https://coins.llama.fi"
DEFILLAMA_STABLECOINS_BASE_URL = "https://stablecoins.llama.fi"
DEFILLAMA_YIELDS_BASE_URL = "https://yields.llama.fi"
DEFILLAMA_VOLUMES_BASE_URL = "https://api.llama.fi"
DEFILLAMA_FEES_BASE_URL = "https://api.llama.fi"


# TVL API Functions
async def fetch_protocols() -> dict:
    """List all protocols on defillama along with their TVL."""
    url = f"{DEFILLAMA_TVL_BASE_URL}/protocols"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_protocol(protocol: str) -> dict:
    """Get historical TVL of a protocol and breakdowns by token and chain."""
    url = f"{DEFILLAMA_TVL_BASE_URL}/protocol/{protocol}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_historical_tvl() -> dict:
    """Get historical TVL of DeFi on all chains."""
    url = f"{DEFILLAMA_TVL_BASE_URL}/v2/historicalChainTvl"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_chain_historical_tvl(chain: str) -> dict:
    """Get historical TVL of a specific chain."""
    url = f"{DEFILLAMA_TVL_BASE_URL}/v2/historicalChainTvl/{chain}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_protocol_current_tvl(protocol: str) -> dict:
    """Get current TVL of a protocol."""
    url = f"{DEFILLAMA_TVL_BASE_URL}/tvl/{protocol}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_chains() -> dict:
    """Get current TVL of all chains."""
    url = f"{DEFILLAMA_TVL_BASE_URL}/v2/chains"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


# Coins API Functions
async def fetch_current_prices(coins: List[str]) -> dict:
    """Get current prices of tokens by contract address using a 4-hour search window."""
    coins_str = ",".join(coins)
    url = f"{DEFILLAMA_COINS_BASE_URL}/prices/current/{coins_str}?searchWidth=4h"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_historical_prices(timestamp: int, coins: List[str]) -> dict:
    """Get historical prices of tokens by contract address using a 4-hour search window."""
    coins_str = ",".join(coins)
    url = f"{DEFILLAMA_COINS_BASE_URL}/prices/historical/{timestamp}/{coins_str}?searchWidth=4h"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_batch_historical_prices(coins_timestamps: dict) -> dict:
    """Get historical prices for multiple tokens at multiple timestamps."""
    url = f"{DEFILLAMA_COINS_BASE_URL}/batchHistorical"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url, params={"coins": coins_timestamps, "searchWidth": "600"}
        )
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_price_chart(coins: List[str]) -> dict:
    """Get historical price chart data from the past day for multiple tokens."""
    coins_str = ",".join(coins)
    start_time = int(datetime.now().timestamp()) - 86400  # now - 1 day

    url = f"{DEFILLAMA_COINS_BASE_URL}/chart/{coins_str}"
    params = {"start": start_time, "span": 10, "period": "2d", "searchWidth": "600"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_price_percentage(coins: List[str]) -> dict:
    """Get price percentage changes for multiple tokens over a 24h period."""
    coins_str = ",".join(coins)
    current_timestamp = int(datetime.now().timestamp())

    url = f"{DEFILLAMA_COINS_BASE_URL}/percentage/{coins_str}"
    params = {"timestamp": current_timestamp, "lookForward": "false", "period": "24h"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_first_price(coins: List[str]) -> dict:
    """Get first recorded price data for multiple tokens."""
    coins_str = ",".join(coins)
    url = f"{DEFILLAMA_COINS_BASE_URL}/prices/first/{coins_str}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_block(chain: str) -> dict:
    """Get current block data for a specific chain."""
    current_timestamp = int(datetime.now().timestamp())
    url = f"{DEFILLAMA_COINS_BASE_URL}/block/{chain}/{current_timestamp}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


# Stablecoins API Functions
async def fetch_stablecoins() -> dict:
    """Get comprehensive stablecoin data from DeFi Llama."""
    url = f"{DEFILLAMA_STABLECOINS_BASE_URL}/stablecoins"
    params = {"includePrices": "true"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_stablecoin_charts(
    stablecoin_id: str, chain: Optional[str] = None
) -> dict:
    """Get historical circulating supply data for a stablecoin."""
    base_url = f"{DEFILLAMA_STABLECOINS_BASE_URL}/stablecoincharts"

    # If chain is specified, fetch chain-specific data, otherwise fetch all chains
    endpoint = f"/{chain}" if chain else "/all"
    url = f"{base_url}{endpoint}?stablecoin={stablecoin_id}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_stablecoin_chains() -> dict:
    """Get stablecoin distribution data across all chains."""
    url = f"{DEFILLAMA_STABLECOINS_BASE_URL}/stablecoinchains"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_stablecoin_prices() -> dict:
    """Get current stablecoin price data.

    Returns:
        Dictionary containing stablecoin prices with their dates
    """
    url = f"{DEFILLAMA_STABLECOINS_BASE_URL}/stablecoinprices"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


# Yields API Functions
async def fetch_pools() -> dict:
    """Get comprehensive data for all yield-generating pools."""
    url = f"{DEFILLAMA_YIELDS_BASE_URL}/pools"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_pool_chart(pool_id: str) -> dict:
    """Get historical chart data for a specific pool."""
    url = f"{DEFILLAMA_YIELDS_BASE_URL}/chart/{pool_id}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


# Volumes API Functions
async def fetch_dex_overview() -> dict:
    """Get overview data for DEX protocols."""
    url = f"{DEFILLAMA_VOLUMES_BASE_URL}/overview/dexs"
    params = {
        "excludeTotalDataChart": "true",
        "excludeTotalDataChartBreakdown": "true",
        "dataType": "dailyVolume",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_dex_summary(protocol: str) -> dict:
    """Get summary data for a specific DEX protocol."""
    url = f"{DEFILLAMA_VOLUMES_BASE_URL}/summary/dexs/{protocol}"
    params = {
        "excludeTotalDataChart": "true",
        "excludeTotalDataChartBreakdown": "true",
        "dataType": "dailyVolume",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


async def fetch_options_overview() -> dict:
    """Get overview data for options protocols from DeFi Llama."""
    url = f"{DEFILLAMA_VOLUMES_BASE_URL}/overview/options"
    params = {
        "excludeTotalDataChart": "true",
        "excludeTotalDataChartBreakdown": "true",
        "dataType": "dailyPremiumVolume",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()


# Fees and Revenue API Functions
async def fetch_fees_overview() -> dict:
    """Get overview data for fees from DeFi Llama.

    Returns:
        Dictionary containing fees overview data
    """
    url = f"{DEFILLAMA_FEES_BASE_URL}/overview/fees"
    params = {
        "excludeTotalDataChart": "true",
        "excludeTotalDataChartBreakdown": "true",
        "dataType": "dailyFees",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
    if response.status_code != 200:
        return {"error": f"API returned status code {response.status_code}"}
    return response.json()
