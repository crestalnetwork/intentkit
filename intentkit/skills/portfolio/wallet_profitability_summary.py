import logging
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.constants import DEFAULT_CHAIN

logger = logging.getLogger(__name__)


class WalletProfitabilitySummaryInput(BaseModel):
    """Input for wallet profitability summary tool."""

    address: str = Field(
        description="The wallet address to get profitability summary for."
    )
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'bsc', 'polygon').",
        default=DEFAULT_CHAIN,
    )
    days: Optional[str] = Field(
        description="Timeframe in days for the profitability summary. Options: 'all', '7', '30', '60', '90'.",
        default="all",
    )


class WalletProfitabilitySummary(PortfolioBaseTool):
    """Tool for retrieving wallet profitability summary using Moralis.

    This tool uses Moralis' API to retrieve a summary of wallet profitability
    based on specified parameters.
    """

    name: str = "portfolio_wallet_profitability_summary"
    description: str = (
        "Retrieve a summary of wallet profitability including total profit/loss, "
        "trade volume, and other metrics. Filter by time period."
    )
    args_schema: Type[BaseModel] = WalletProfitabilitySummaryInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        days: Optional[str] = "all",
        **kwargs,
    ) -> Dict[str, Any]:
        """Fetch wallet profitability summary from Moralis.

        Args:
            address: The wallet address to get profitability for
            chain: The blockchain to query
            days: Timeframe in days for the summary
            config: The configuration for the tool call

        Returns:
            Dict containing wallet profitability summary data
        """
        context = self.get_context()
        logger.debug(
            f"wallet_profitability_summary.py: Fetching profitability summary with context {context}"
        )

        # Get the API key from the agent's configuration
        api_key = self.get_api_key()
        if not api_key:
            return {"error": "No Moralis API key provided in the configuration."}

        # Build query parameters
        params = {
            "chain": chain,
            "days": days,
        }

        # Call Moralis API
        try:
            endpoint = f"/wallets/{address}/profitability/summary"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except Exception as e:
            logger.error(
                f"wallet_profitability_summary.py: Error fetching profitability summary: {e}",
                exc_info=True,
            )
            return {
                "error": "An error occurred while fetching profitability summary. Please try again later."
            }
