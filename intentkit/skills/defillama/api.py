"""DeFi Llama API implementation and shared schemas."""

from datetime import datetime
from typing import Any

import httpx
from langchain_core.tools.base import ToolException

DEFILLAMA_TVL_BASE_URL = "https://api.llama.fi"
DEFILLAMA_COINS_BASE_URL = "https://coins.llama.fi"
DEFILLAMA_STABLECOINS_BASE_URL = "https://stablecoins.llama.fi"
DEFILLAMA_YIELDS_BASE_URL = "https://yields.llama.fi"
DEFILLAMA_VOLUMES_BASE_URL = "https://api.llama.fi"
DEFILLAMA_FEES_BASE_URL = "https://api.llama.fi"


async def _get(url: str, params: dict[str, Any] | None = None) -> Any:
    """Make a GET request and raise on error."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
    if response.status_code != 200:
        raise ToolException(
            f"DeFi Llama API returned status code {response.status_code}"
        )
    return response.json()


# TVL API Functions
async def fetch_protocols() -> Any:
    """List all protocols on defillama along with their TVL."""
    return await _get(f"{DEFILLAMA_TVL_BASE_URL}/protocols")


async def fetch_protocol(protocol: str) -> dict[str, Any]:
    """Get historical TVL of a protocol and breakdowns by token and chain."""
    return await _get(f"{DEFILLAMA_TVL_BASE_URL}/protocol/{protocol}")


async def fetch_historical_tvl() -> Any:
    """Get historical TVL of DeFi on all chains."""
    return await _get(f"{DEFILLAMA_TVL_BASE_URL}/v2/historicalChainTvl")


async def fetch_chain_historical_tvl(chain: str) -> Any:
    """Get historical TVL of a specific chain."""
    return await _get(f"{DEFILLAMA_TVL_BASE_URL}/v2/historicalChainTvl/{chain}")


async def fetch_protocol_current_tvl(protocol: str) -> Any:
    """Get current TVL of a protocol."""
    return await _get(f"{DEFILLAMA_TVL_BASE_URL}/tvl/{protocol}")


async def fetch_chains() -> Any:
    """Get current TVL of all chains."""
    return await _get(f"{DEFILLAMA_TVL_BASE_URL}/v2/chains")


# Coins API Functions
async def fetch_current_prices(coins: list[str]) -> dict[str, Any]:
    """Get current prices of tokens by contract address using a 4-hour search window."""
    coins_str = ",".join(coins)
    return await _get(
        f"{DEFILLAMA_COINS_BASE_URL}/prices/current/{coins_str}?searchWidth=4h"
    )


async def fetch_historical_prices(timestamp: int, coins: list[str]) -> dict[str, Any]:
    """Get historical prices of tokens by contract address using a 4-hour search window."""
    coins_str = ",".join(coins)
    return await _get(
        f"{DEFILLAMA_COINS_BASE_URL}/prices/historical/{timestamp}/{coins_str}?searchWidth=4h"
    )


async def fetch_batch_historical_prices(
    coins_timestamps: dict[str, Any],
) -> dict[str, Any]:
    """Get historical prices for multiple tokens at multiple timestamps."""
    return await _get(
        f"{DEFILLAMA_COINS_BASE_URL}/batchHistorical",
        params={"coins": coins_timestamps, "searchWidth": "600"},
    )


async def fetch_price_chart(coins: list[str]) -> dict[str, Any]:
    """Get historical price chart data from the past day for multiple tokens."""
    coins_str = ",".join(coins)
    start_time = int(datetime.now().timestamp()) - 86400  # now - 1 day
    return await _get(
        f"{DEFILLAMA_COINS_BASE_URL}/chart/{coins_str}",
        params={"start": start_time, "span": 10, "period": "2d", "searchWidth": "600"},
    )


async def fetch_price_percentage(coins: list[str]) -> dict[str, Any]:
    """Get price percentage changes for multiple tokens over a 24h period."""
    coins_str = ",".join(coins)
    current_timestamp = int(datetime.now().timestamp())
    return await _get(
        f"{DEFILLAMA_COINS_BASE_URL}/percentage/{coins_str}",
        params={
            "timestamp": current_timestamp,
            "lookForward": "false",
            "period": "24h",
        },
    )


async def fetch_first_price(coins: list[str]) -> dict[str, Any]:
    """Get first recorded price data for multiple tokens."""
    coins_str = ",".join(coins)
    return await _get(f"{DEFILLAMA_COINS_BASE_URL}/prices/first/{coins_str}")


async def fetch_block(chain: str) -> dict[str, Any]:
    """Get current block data for a specific chain."""
    current_timestamp = int(datetime.now().timestamp())
    return await _get(f"{DEFILLAMA_COINS_BASE_URL}/block/{chain}/{current_timestamp}")


# Stablecoins API Functions
async def fetch_stablecoins() -> dict[str, Any]:
    """Get comprehensive stablecoin data from DeFi Llama."""
    return await _get(
        f"{DEFILLAMA_STABLECOINS_BASE_URL}/stablecoins",
        params={"includePrices": "true"},
    )


async def fetch_stablecoin_charts(stablecoin_id: str, chain: str | None = None) -> Any:
    """Get historical circulating supply data for a stablecoin."""
    endpoint = f"/{chain}" if chain else "/all"
    return await _get(
        f"{DEFILLAMA_STABLECOINS_BASE_URL}/stablecoincharts{endpoint}?stablecoin={stablecoin_id}"
    )


async def fetch_stablecoin_chains() -> Any:
    """Get stablecoin distribution data across all chains."""
    return await _get(f"{DEFILLAMA_STABLECOINS_BASE_URL}/stablecoinchains")


async def fetch_stablecoin_prices() -> dict[str, Any]:
    """Get current stablecoin price data."""
    return await _get(f"{DEFILLAMA_STABLECOINS_BASE_URL}/stablecoinprices")


# Yields API Functions
async def fetch_pools() -> dict[str, Any]:
    """Get comprehensive data for all yield-generating pools."""
    return await _get(f"{DEFILLAMA_YIELDS_BASE_URL}/pools")


async def fetch_pool_chart(pool_id: str) -> Any:
    """Get historical chart data for a specific pool."""
    return await _get(f"{DEFILLAMA_YIELDS_BASE_URL}/chart/{pool_id}")


# Volumes API Functions
async def fetch_dex_overview() -> dict[str, Any]:
    """Get overview data for DEX protocols."""
    return await _get(
        f"{DEFILLAMA_VOLUMES_BASE_URL}/overview/dexs",
        params={
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyVolume",
        },
    )


async def fetch_dex_summary(protocol: str) -> dict[str, Any]:
    """Get summary data for a specific DEX protocol."""
    return await _get(
        f"{DEFILLAMA_VOLUMES_BASE_URL}/summary/dexs/{protocol}",
        params={
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyVolume",
        },
    )


async def fetch_options_overview() -> dict[str, Any]:
    """Get overview data for options protocols from DeFi Llama."""
    return await _get(
        f"{DEFILLAMA_VOLUMES_BASE_URL}/overview/options",
        params={
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyPremiumVolume",
        },
    )


# Fees and Revenue API Functions
async def fetch_fees_overview() -> dict[str, Any]:
    """Get overview data for fees from DeFi Llama."""
    return await _get(
        f"{DEFILLAMA_FEES_BASE_URL}/overview/fees",
        params={
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyFees",
        },
    )
