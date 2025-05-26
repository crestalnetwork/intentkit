import logging
from typing import Any, Dict, Optional, Type

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.portfolio.base import PortfolioBaseTool
from skills.portfolio.constants import (
    DEFAULT_CHAIN,
    DEFAULT_LIMIT,
)

logger = logging.getLogger(__name__)


class WalletApprovalsInput(BaseModel):
    """Input for wallet token approvals tool."""

    address: str = Field(description="The wallet address to check token approvals for.")
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'bsc', 'polygon').",
        default=DEFAULT_CHAIN,
    )
    cursor: Optional[str] = Field(
        description="The cursor for pagination.",
        default=None,
    )
    limit: Optional[int] = Field(
        description="The number of results per page.",
        default=DEFAULT_LIMIT,
    )


class WalletApprovals(PortfolioBaseTool):
    """Tool for retrieving token approvals for a wallet using Moralis.

    This tool uses Moralis' API to fetch active ERC20 token approvals for the
    specified wallet address.
    """

    name: str = "portfolio_wallet_approvals"
    description: str = (
        "Retrieve active ERC20 token approvals for the specified wallet address. "
        "This helps identify which contracts have permission to spend tokens."
    )
    args_schema: Type[BaseModel] = WalletApprovalsInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        cursor: Optional[str] = None,
        limit: Optional[int] = DEFAULT_LIMIT,
        config: RunnableConfig = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Fetch wallet token approvals from Moralis.

        Args:
            address: The wallet address to get approvals for
            chain: The blockchain to query
            cursor: Pagination cursor
            limit: Number of results per page
            config: The configuration for the tool call

        Returns:
            Dict containing wallet approvals data
        """
        context = self.context_from_config(config)
        logger.debug(
            f"wallet_approvals.py: Fetching wallet approvals with context {context}"
        )

        # Get the API key from the agent's configuration
        api_key = self.get_api_key(context)
        if not api_key:
            return {"error": "No Moralis API key provided in the configuration."}

        # Build query parameters
        params = {
            "chain": chain,
            "limit": limit,
        }

        # Add optional parameters if they exist
        if cursor:
            params["cursor"] = cursor

        # Call Moralis API
        try:
            endpoint = f"/wallets/{address}/approvals"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except Exception as e:
            logger.error(
                f"wallet_approvals.py: Error fetching wallet approvals: {e}",
                exc_info=True,
            )
            return {
                "error": "An error occurred while fetching wallet approvals. Please try again later."
            }
