import logging
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.token.base import TokenBaseTool
from intentkit.skills.token.constants import DEFAULT_CHAIN, DEFAULT_LIMIT, DEFAULT_ORDER

logger = logging.getLogger(__name__)


class ERC20TransfersInput(BaseModel):
    """Input for ERC20 transfers tool."""

    address: str = Field(description="Wallet address.")
    chain: str = Field(
        description="Chain to query, e.g. 'eth', 'bsc', 'polygon'.",
        default=DEFAULT_CHAIN,
    )
    contract_addresses: list[str] | None = Field(
        description="Filter by contract addresses.",
        default=None,
    )
    from_block: int | None = Field(
        description="Minimum block number.",
        default=None,
    )
    to_block: int | None = Field(
        description="Maximum block number.",
        default=None,
    )
    from_date: str | None = Field(
        description="Start date filter.",
        default=None,
    )
    to_date: str | None = Field(
        description="End date filter.",
        default=None,
    )
    limit: int | None = Field(
        description="Page size.",
        default=DEFAULT_LIMIT,
    )
    order: str | None = Field(
        description="Sort order: ASC or DESC.",
        default=DEFAULT_ORDER,
    )
    cursor: str | None = Field(
        description="Pagination cursor.",
        default=None,
    )


class ERC20Transfers(TokenBaseTool):
    """Tool for retrieving ERC20 token transfers by wallet using Moralis.

    This tool uses Moralis' API to fetch ERC20 token transactions ordered by
    block number in descending order for a specific wallet address.
    """

    name: str = "token_erc20_transfers"
    description: str = "Get ERC20 token transfers for a wallet address."
    args_schema: ArgsSchema | None = ERC20TransfersInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        contract_addresses: list[str] | None = None,
        from_block: int | None = None,
        to_block: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int | None = DEFAULT_LIMIT,
        order: str | None = DEFAULT_ORDER,
        cursor: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Fetch ERC20 token transfers for a wallet from Moralis.

        Args:
            address: The wallet address
            chain: The blockchain to query
            contract_addresses: List of contract addresses to filter by
            from_block: Minimum block number
            to_block: Maximum block number
            from_date: Start date for transfers
            to_date: End date for transfers
            limit: Number of results per page
            order: Order of results (ASC/DESC)
            cursor: Pagination cursor
            config: The configuration for the tool call

        Returns:
            Dict containing ERC20 transfer data
        """
        context = self.get_context()
        if context is None:
            logger.error("Context is None, cannot retrieve API key")
            return {
                "error": "Cannot retrieve API key. Please check agent configuration."
            }

        # Get the API key
        api_key = self.get_api_key()

        if not api_key:
            logger.error("No Moralis API key available")
            return {"error": "No Moralis API key provided in the configuration."}

        # Build query parameters
        params: dict[str, Any] = {"chain": chain, "limit": limit, "order": order}

        # Add optional parameters if they exist
        if contract_addresses:
            params["contract_addresses"] = contract_addresses
        if from_block:
            params["from_block"] = from_block
        if to_block:
            params["to_block"] = to_block
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if cursor:
            params["cursor"] = cursor

        # Call Moralis API
        try:
            endpoint = f"/{address}/erc20/transfers"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except Exception as e:
            logger.error("Error fetching ERC20 transfers: %s", e)
            return {
                "error": f"An error occurred while fetching ERC20 transfers: {str(e)}. Please try again later."
            }
