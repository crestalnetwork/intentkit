import logging
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.token.base import TokenBaseTool

logger = logging.getLogger(__name__)


class TokenSearchInput(BaseModel):
    """Input for token search tool."""

    query: str = Field(
        description="Search query - can be token address, token name or token symbol."
    )
    chains: Optional[List[str]] = Field(
        description="The chain(s) to query (e.g., 'eth', 'bsc', 'polygon').",
        default=None,
    )
    limit: Optional[int] = Field(
        description="The desired page size of the result.",
        default=None,
    )
    is_verified_contract: Optional[bool] = Field(
        description="Whether the contract is verified.",
        default=None,
    )


class TokenSearch(TokenBaseTool):
    """Tool for searching tokens using Moralis.

    This tool uses Moralis' premium API to search for tokens based on contract address,
    token name or token symbol.

    NOTE: To use this API, you will need an API key associated with a Moralis account
    on the Business plan or a custom Enterprise plan.
    """

    name: str = "token_search"
    description: str = (
        "Search for tokens based on contract address, token name or token symbol. "
        "Returns token information including price, market cap, and security information. "
        "NOTE: This is a premium endpoint that requires a Moralis Business plan."
    )
    args_schema: Type[BaseModel] = TokenSearchInput

    async def _arun(
        self,
        query: str,
        chains: Optional[List[str]] = None,
        limit: Optional[int] = None,
        is_verified_contract: Optional[bool] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Search for tokens using Moralis.

        Args:
            query: Search query (address, name, or symbol)
            chains: The blockchains to query
            limit: Number of results
            is_verified_contract: Filter for verified contracts
            config: The configuration for the tool call

        Returns:
            Dict containing token search results
        """
        # Extract context from config
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
        params = {"query": query}

        # Add optional parameters if they exist
        if chains:
            params["chains"] = ",".join(chains)
        if limit:
            params["limit"] = limit
        if is_verified_contract is not None:
            params["isVerifiedContract"] = is_verified_contract

        # Call Moralis API
        try:
            endpoint = "/tokens/search"
            result = await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )

            # Add premium notice if there's an error that might be related to plan limits
            if "error" in result and "403" in str(result.get("error", "")):
                logger.error("Received 403 error - likely a plan limitation")
                result["notice"] = (
                    "This API requires a Moralis Business plan or Enterprise plan. "
                    "Please ensure your API key is associated with the appropriate plan."
                )

            return result
        except Exception as e:
            logger.error(f"Error searching for tokens: {e}")
            return {
                "error": f"An error occurred while searching for tokens: {str(e)}. Please try again later.",
                "notice": (
                    "This API requires a Moralis Business plan or Enterprise plan. "
                    "Please ensure your API key is associated with the appropriate plan."
                ),
            }
