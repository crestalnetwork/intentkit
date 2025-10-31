import logging
from typing import Any

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.constants import DEFAULT_CHAIN

logger = logging.getLogger(__name__)


class WalletProfitabilityInput(BaseModel):
    """Input for wallet profitability breakdown tool."""

    address: str = Field(
        description="The wallet address to get profitability breakdown for."
    )
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'bsc', 'polygon').",
        default=DEFAULT_CHAIN,
    )
    days: str | None = Field(
        description="Timeframe in days for which profitability is calculated. Options: 'all', '7', '30', '60', '90'.",
        default="all",
    )
    token_addresses: list[str] | None = Field(
        description="The token addresses list to filter the result with.",
        default=None,
    )


class WalletProfitability(PortfolioBaseTool):
    """Tool for retrieving detailed wallet profitability breakdown using Moralis.

    This tool uses Moralis' API to retrieve detailed profitability information for a
    specific wallet address, with the option to filter by one or more tokens.
    """

    name: str = "portfolio_wallet_profitability"
    description: str = (
        "Retrieve detailed profitability breakdown for a wallet, including profit/loss per token, "
        "average buy/sell prices, and realized profits. Can be filtered by specific tokens."
    )
    args_schema: type[BaseModel] = WalletProfitabilityInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        days: str | None = "all",
        token_addresses: list[str] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Fetch detailed wallet profitability from Moralis.

        Args:
            address: The wallet address to get profitability for
            chain: The blockchain to query
            days: Timeframe in days for the profitability data
            token_addresses: List of token addresses to filter results
            config: The configuration for the tool call

        Returns:
            Dict containing wallet profitability breakdown data
        """
        context = self.get_context()
        logger.debug(
            f"wallet_profitability.py: Fetching profitability breakdown with context {context}"
        )

        # Build query parameters
        params = {
            "chain": chain,
            "days": days,
        }

        # Add token_addresses if specified
        if token_addresses:
            params["token_addresses"] = token_addresses

        # Call Moralis API
        api_key = self.get_api_key()

        try:
            endpoint = f"/wallets/{address}/profitability"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except ToolException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "wallet_profitability.py: Error fetching profitability breakdown",
                exc_info=exc,
            )
            raise ToolException(
                "An unexpected error occurred while fetching profitability breakdown."
            ) from exc
