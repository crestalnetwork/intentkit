import logging
from typing import Any

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.constants import (
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
    cursor: str | None = Field(
        description="The cursor for pagination.",
        default=None,
    )
    limit: int | None = Field(
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
    args_schema: type[BaseModel] = WalletApprovalsInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        cursor: str | None = None,
        limit: int | None = DEFAULT_LIMIT,
        **kwargs,
    ) -> dict[str, Any]:
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
        context = self.get_context()
        logger.debug(
            f"wallet_approvals.py: Fetching wallet approvals with context {context}"
        )

        # Build query parameters
        params = {
            "chain": chain,
            "limit": limit,
        }

        # Add optional parameters if they exist
        if cursor:
            params["cursor"] = cursor

        # Call Moralis API
        api_key = self.get_api_key()

        try:
            endpoint = f"/wallets/{address}/approvals"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except ToolException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "wallet_approvals.py: Error fetching wallet approvals", exc_info=exc
            )
            raise ToolException(
                "An unexpected error occurred while fetching wallet approvals."
            ) from exc
