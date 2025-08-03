import logging
from typing import Any, Dict, Type

from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.constants import DEFAULT_CHAIN

logger = logging.getLogger(__name__)


class WalletStatsInput(BaseModel):
    """Input for wallet stats tool."""

    address: str = Field(description="The wallet address to get stats for.")
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'bsc', 'polygon').",
        default=DEFAULT_CHAIN,
    )


class WalletStats(PortfolioBaseTool):
    """Tool for retrieving wallet statistics using Moralis.

    This tool uses Moralis' API to get high-level statistical information about
    a wallet, including NFT counts, collection counts, and transaction counts.
    """

    name: str = "portfolio_wallet_stats"
    description: str = (
        "Get statistical information about a wallet, including the number of NFTs, "
        "collections, and transaction counts."
    )
    args_schema: Type[BaseModel] = WalletStatsInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        **kwargs,
    ) -> Dict[str, Any]:
        """Fetch wallet stats from Moralis.

        Args:
            address: The wallet address to get stats for
            chain: The blockchain to query
            config: The configuration for the tool call

        Returns:
            Dict containing wallet stats data
        """
        context = self.get_context()
        logger.debug(f"wallet_stats.py: Fetching wallet stats with context {context}")

        # Get the API key from the agent's configuration
        api_key = self.get_api_key()
        if not api_key:
            return {"error": "No Moralis API key provided in the configuration."}

        # Build query parameters
        params = {
            "chain": chain,
        }

        # Call Moralis API
        try:
            endpoint = f"/wallets/{address}/stats"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except Exception as e:
            logger.error(
                f"wallet_stats.py: Error fetching wallet stats: {e}", exc_info=True
            )
            return {
                "error": "An error occurred while fetching wallet stats. Please try again later."
            }
