"""DeFi Llama tools."""

import logging
from collections.abc import Callable

from intentkit.tools.defillama.base import DefiLlamaBaseTool
from intentkit.tools.defillama.coins.fetch_batch_historical_prices import (
    DefiLlamaFetchBatchHistoricalPrices,
)
from intentkit.tools.defillama.coins.fetch_block import DefiLlamaFetchBlock

# Coins Tools
from intentkit.tools.defillama.coins.fetch_current_prices import (
    DefiLlamaFetchCurrentPrices,
)
from intentkit.tools.defillama.coins.fetch_first_price import DefiLlamaFetchFirstPrice
from intentkit.tools.defillama.coins.fetch_historical_prices import (
    DefiLlamaFetchHistoricalPrices,
)
from intentkit.tools.defillama.coins.fetch_price_chart import DefiLlamaFetchPriceChart
from intentkit.tools.defillama.coins.fetch_price_percentage import (
    DefiLlamaFetchPricePercentage,
)

# Fees Tools
from intentkit.tools.defillama.fees.fetch_fees_overview import (
    DefiLlamaFetchFeesOverview,
)
from intentkit.tools.defillama.stablecoins.fetch_stablecoin_chains import (
    DefiLlamaFetchStablecoinChains,
)
from intentkit.tools.defillama.stablecoins.fetch_stablecoin_charts import (
    DefiLlamaFetchStablecoinCharts,
)
from intentkit.tools.defillama.stablecoins.fetch_stablecoin_prices import (
    DefiLlamaFetchStablecoinPrices,
)

# Stablecoins Tools
from intentkit.tools.defillama.stablecoins.fetch_stablecoins import (
    DefiLlamaFetchStablecoins,
)
from intentkit.tools.defillama.tvl.fetch_chain_historical_tvl import (
    DefiLlamaFetchChainHistoricalTvl,
)
from intentkit.tools.defillama.tvl.fetch_chains import DefiLlamaFetchChains
from intentkit.tools.defillama.tvl.fetch_historical_tvl import (
    DefiLlamaFetchHistoricalTvl,
)
from intentkit.tools.defillama.tvl.fetch_protocol import DefiLlamaFetchProtocol
from intentkit.tools.defillama.tvl.fetch_protocol_current_tvl import (
    DefiLlamaFetchProtocolCurrentTvl,
)

# TVL Tools
from intentkit.tools.defillama.tvl.fetch_protocols import DefiLlamaFetchProtocols

# Volumes Tools
from intentkit.tools.defillama.volumes.fetch_dex_overview import (
    DefiLlamaFetchDexOverview,
)
from intentkit.tools.defillama.volumes.fetch_dex_summary import (
    DefiLlamaFetchDexSummary,
)
from intentkit.tools.defillama.volumes.fetch_options_overview import (
    DefiLlamaFetchOptionsOverview,
)
from intentkit.tools.defillama.yields.fetch_pool_chart import DefiLlamaFetchPoolChart

# Yields Tools
from intentkit.tools.defillama.yields.fetch_pools import DefiLlamaFetchPools
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="DeFiLlama",
    description="Integration with DeFi Llama API providing comprehensive decentralized finance data including token prices, protocol TVL, DEX volumes, and stablecoin metrics",
    tags=["Analytics", "DeFi"],
    icon="/tools/defillama/defillama.jpeg",
)


# we cache tools in system level, because they are stateless
_cache: dict[str, DefiLlamaBaseTool] = {}

logger = logging.getLogger(__name__)

# Each tool maps to a specific DeFi Llama API endpoint. Some tools handle both
# base and chain-specific endpoints through optional parameters rather than
# separate implementations.
_TOOL_CLASSES: dict[str, Callable[[], DefiLlamaBaseTool]] = {
    # TVL Tools
    "defillama_fetch_protocols": DefiLlamaFetchProtocols,
    "defillama_fetch_protocol": DefiLlamaFetchProtocol,
    "defillama_fetch_total_historical_tvl": DefiLlamaFetchHistoricalTvl,
    "defillama_fetch_chain_historical_tvl": DefiLlamaFetchChainHistoricalTvl,
    "defillama_fetch_protocol_tvl": DefiLlamaFetchProtocolCurrentTvl,
    "defillama_fetch_chains": DefiLlamaFetchChains,
    # Coins Tools
    "defillama_fetch_current_prices": DefiLlamaFetchCurrentPrices,
    "defillama_fetch_historical_prices": DefiLlamaFetchHistoricalPrices,
    "defillama_fetch_batch_historical_prices": DefiLlamaFetchBatchHistoricalPrices,
    "defillama_fetch_price_chart": DefiLlamaFetchPriceChart,
    "defillama_fetch_price_percentage": DefiLlamaFetchPricePercentage,
    "defillama_fetch_first_price": DefiLlamaFetchFirstPrice,
    "defillama_fetch_block": DefiLlamaFetchBlock,
    # Stablecoins Tools
    "defillama_fetch_stablecoins": DefiLlamaFetchStablecoins,
    "defillama_fetch_stablecoin_charts": DefiLlamaFetchStablecoinCharts,
    "defillama_fetch_stablecoin_chains": DefiLlamaFetchStablecoinChains,
    "defillama_fetch_stablecoin_prices": DefiLlamaFetchStablecoinPrices,
    # Yields Tools
    "defillama_fetch_pools": DefiLlamaFetchPools,
    "defillama_fetch_pool_chart": DefiLlamaFetchPoolChart,
    # Volumes Tools
    "defillama_fetch_dex_overview": DefiLlamaFetchDexOverview,
    "defillama_fetch_dex_summary": DefiLlamaFetchDexSummary,
    "defillama_fetch_options_overview": DefiLlamaFetchOptionsOverview,
    # Fees Tools
    "defillama_fetch_fees_overview": DefiLlamaFetchFeesOverview,
}


async def get_tools(tool_names: list[str], **_) -> list[DefiLlamaBaseTool]:
    """Get the requested DeFi Llama tools."""
    return [tool for name in tool_names if (tool := get_defillama_tool(name))]


def get_defillama_tool(tool_name: str) -> DefiLlamaBaseTool | None:
    """Get a DeFi Llama tool by name."""
    if tool_name not in _cache:
        tool_class = _TOOL_CLASSES.get(tool_name)
        if tool_class is None:
            logger.warning("Unknown DeFi Llama tool: %s", tool_name)
            return None
        _cache[tool_name] = tool_class()
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
