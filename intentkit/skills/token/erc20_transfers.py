import logging
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.token.base import TokenBaseTool
from intentkit.skills.token.constants import DEFAULT_CHAIN, DEFAULT_LIMIT, DEFAULT_ORDER

logger = logging.getLogger(__name__)


class ERC20TransfersInput(BaseModel):
    """Input for ERC20 transfers tool."""

    address: str = Field(
        description="The address of the wallet to get ERC20 token transfers for."
    )
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'bsc', 'polygon').",
        default=DEFAULT_CHAIN,
    )
    contract_addresses: Optional[List[str]] = Field(
        description="List of contract addresses of transfers to filter by.",
        default=None,
    )
    from_block: Optional[int] = Field(
        description="The minimum block number from which to get the transactions.",
        default=None,
    )
    to_block: Optional[int] = Field(
        description="The maximum block number from which to get the transactions.",
        default=None,
    )
    from_date: Optional[str] = Field(
        description="The start date from which to get the transactions (any format accepted by momentjs).",
        default=None,
    )
    to_date: Optional[str] = Field(
        description="Get the transactions up to this date (any format accepted by momentjs).",
        default=None,
    )
    limit: Optional[int] = Field(
        description="The desired page size of the result.",
        default=DEFAULT_LIMIT,
    )
    order: Optional[str] = Field(
        description="The order of the result, in ascending (ASC) or descending (DESC).",
        default=DEFAULT_ORDER,
    )
    cursor: Optional[str] = Field(
        description="The cursor returned in the previous response (for pagination).",
        default=None,
    )


class ERC20Transfers(TokenBaseTool):
    """Tool for retrieving ERC20 token transfers by wallet using Moralis.

    This tool uses Moralis' API to fetch ERC20 token transactions ordered by
    block number in descending order for a specific wallet address.
    """

    name: str = "token_erc20_transfers"
    description: str = (
        "Get ERC20 token transactions for a wallet address, ordered by block number. "
        "Returns transaction details, token information, and wallet interactions."
    )
    args_schema: Type[BaseModel] = ERC20TransfersInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        contract_addresses: Optional[List[str]] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: Optional[int] = DEFAULT_LIMIT,
        order: Optional[str] = DEFAULT_ORDER,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
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
        params = {"chain": chain, "limit": limit, "order": order}

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
            logger.error(f"Error fetching ERC20 transfers: {e}")
            return {
                "error": f"An error occurred while fetching ERC20 transfers: {str(e)}. Please try again later."
            }
