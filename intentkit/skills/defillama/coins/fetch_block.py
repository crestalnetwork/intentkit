"""Tool for fetching current block data via DeFi Llama API."""

from typing import Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_block
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_BLOCK_PROMPT = """
This tool fetches current block data from DeFi Llama for a specific chain.
Provide:
- Chain name (e.g. "ethereum", "bsc", "solana")
Returns:
- Block height
- Block timestamp
"""


class BlockData(BaseModel):
    """Model representing block data."""

    height: int = Field(..., description="Block height number")
    timestamp: int = Field(..., description="Unix timestamp of the block")


class FetchBlockInput(BaseModel):
    """Input schema for fetching block data."""

    chain: str = Field(..., description="Chain name to fetch block data for")


class FetchBlockResponse(BaseModel):
    """Response schema for block data."""

    chain: str = Field(..., description="Normalized chain name")
    height: Optional[int] = Field(None, description="Block height number")
    timestamp: Optional[int] = Field(None, description="Unix timestamp of the block")
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchBlock(DefiLlamaBaseTool):
    """Tool for fetching current block data from DeFi Llama.

    This tool retrieves current block data for a specific chain.

    Example:
        block_tool = DefiLlamaFetchBlock(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await block_tool._arun(chain="ethereum")
    """

    name: str = "defillama_fetch_block"
    description: str = FETCH_BLOCK_PROMPT
    args_schema: Type[BaseModel] = FetchBlockInput

    async def _arun(self, chain: str) -> FetchBlockResponse:
        """Fetch current block data for the given chain.

        Args:
            config: Runnable configuration
            chain: Chain name to fetch block data for

        Returns:
            FetchBlockResponse containing block data or error
        """
        try:
            # Validate chain parameter
            is_valid, normalized_chain = await self.validate_chain(chain)
            if not is_valid or normalized_chain is None:
                return FetchBlockResponse(chain=chain, error=f"Invalid chain: {chain}")

            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchBlockResponse(chain=normalized_chain, error=error_msg)

            # Fetch block data from API
            result = await fetch_block(chain=normalized_chain)

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchBlockResponse(chain=normalized_chain, error=result["error"])

            # Return the response matching the API structure
            return FetchBlockResponse(
                chain=normalized_chain,
                height=result["height"],
                timestamp=result["timestamp"],
            )

        except Exception as e:
            return FetchBlockResponse(chain=chain, error=str(e))
