import logging
from typing import Any, Dict, Type

from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.constants import DEFAULT_CHAIN

logger = logging.getLogger(__name__)


class WalletDefiPositionsInput(BaseModel):
    """Input for wallet DeFi positions tool."""

    address: str = Field(description="The wallet address to get DeFi positions for.")
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'bsc', 'polygon').",
        default=DEFAULT_CHAIN,
    )


class WalletDefiPositions(PortfolioBaseTool):
    """Tool for retrieving DeFi positions by wallet using Moralis.

    This tool uses Moralis' API to fetch the positions summary of a wallet address,
    including liquidity positions, staking, lending, and other DeFi activities.
    """

    name: str = "portfolio_wallet_defi_positions"
    description: str = (
        "Get the DeFi positions summary of a wallet address. "
        "Returns information about liquidity positions, staking, lending, and other DeFi activities."
    )
    args_schema: Type[BaseModel] = WalletDefiPositionsInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        **kwargs,
    ) -> Dict[str, Any]:
        """Fetch wallet DeFi positions from Moralis.

        Args:
            address: The wallet address
            chain: The blockchain to query
            config: The configuration for the tool call

        Returns:
            Dict containing DeFi positions data
        """
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        logger.debug(
            f"wallet_defi_positions.py: Fetching wallet DeFi positions with context {context}"
        )

        # Get the API key from the agent's configuration
        api_key = skill_config.get("api_key")
        if not api_key:
            return {"error": "No Moralis API key provided in the configuration."}

        # Build query parameters
        params = {"chain": chain}

        # Call Moralis API
        try:
            endpoint = f"/wallets/{address}/defi/positions"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except Exception as e:
            logger.error(
                f"wallet_defi_positions.py: Error fetching wallet DeFi positions: {e}",
                exc_info=True,
            )
            return {
                "error": "An error occurred while fetching wallet DeFi positions. Please try again later."
            }
