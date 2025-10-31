import logging
from typing import Any

from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool

logger = logging.getLogger(__name__)


class WalletNetWorthInput(BaseModel):
    """Input for wallet net worth tool."""

    address: str = Field(description="The wallet address to calculate net worth for.")
    chains: list[str] | None = Field(
        description="The chains to query (e.g., ['eth', 'bsc', 'polygon']).",
        default=None,
    )
    exclude_spam: bool | None = Field(
        description="Exclude spam tokens from the result.",
        default=True,
    )
    exclude_unverified_contracts: bool | None = Field(
        description="Exclude unverified contracts from the result.",
        default=True,
    )
    max_token_inactivity: int | None = Field(
        description="Exclude tokens inactive for more than the given amount of days.",
        default=1,
    )
    min_pair_side_liquidity_usd: float | None = Field(
        description="Exclude tokens with liquidity less than the specified amount in USD.",
        default=1000,
    )


class WalletNetWorth(PortfolioBaseTool):
    """Tool for calculating a wallet's total net worth using Moralis.

    This tool uses Moralis' API to calculate the net worth of a wallet in USD across
    multiple chains, with options to filter out spam and low-liquidity tokens.
    """

    name: str = "portfolio_wallet_net_worth"
    description: str = (
        "Get the net worth of a wallet in USD across multiple chains. "
        "Filters out spam tokens and low-liquidity assets for more accurate results."
    )
    args_schema: type[BaseModel] = WalletNetWorthInput

    async def _arun(
        self,
        address: str,
        chains: list[str] | None = None,
        exclude_spam: bool | None = True,
        exclude_unverified_contracts: bool | None = True,
        max_token_inactivity: int | None = 1,
        min_pair_side_liquidity_usd: float | None = 1000,
        **kwargs,
    ) -> dict[str, Any]:
        """Calculate wallet net worth from Moralis.

        Args:
            address: The wallet address to calculate net worth for
            chains: List of chains to query
            exclude_spam: Whether to exclude spam tokens
            exclude_unverified_contracts: Whether to exclude unverified contracts
            max_token_inactivity: Exclude tokens inactive for more than the given days
            min_pair_side_liquidity_usd: Exclude tokens with liquidity less than specified
            config: The configuration for the tool call

        Returns:
            Dict containing wallet net worth data
        """
        context = self.get_context()
        logger.debug(
            f"wallet_net_worth.py: Calculating wallet net worth with context {context}"
        )

        # Get the API key from the agent's configuration
        api_key = self.get_api_key()
        if not api_key:
            return {"error": "No Moralis API key provided in the configuration."}

        # Build query parameters
        params = {
            "exclude_spam": exclude_spam,
            "exclude_unverified_contracts": exclude_unverified_contracts,
            "max_token_inactivity": max_token_inactivity,
            "min_pair_side_liquidity_usd": min_pair_side_liquidity_usd,
        }

        # Add chains if specified
        if chains:
            params["chains"] = chains

        # Call Moralis API
        try:
            endpoint = f"/wallets/{address}/net-worth"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except Exception as e:
            logger.error(
                f"wallet_net_worth.py: Error calculating wallet net worth: {e}",
                exc_info=True,
            )
            return {
                "error": "An error occurred while calculating wallet net worth. Please try again later."
            }
