"""Tool for fetching protocol TVL via DeFiLlama API."""

from typing import Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_protocol_current_tvl
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_TVL_PROMPT = """
This tool fetches the current Total Value Locked (TVL) for a specific DeFi protocol.
Provide the protocol slug (e.g., "aave", "curve") to get its current TVL in USD.
Returns the normalized protocol name and its TVL value.
"""


class FetchProtocolCurrentTVLInput(BaseModel):
    """Input schema for fetching current protocol TVL."""

    protocol: str = Field(
        ..., description="Protocol slug to fetch TVL for (e.g., 'aave', 'curve')"
    )


class FetchProtocolCurrentTVLResponse(BaseModel):
    """Response schema for current protocol TVL."""

    protocol: str = Field(..., description="Normalized protocol slug")
    tvl: float = Field(..., description="Current Total Value Locked in USD")
    error: str | None = Field(default=None, description="Error message if any")


class DefiLlamaFetchProtocolCurrentTvl(DefiLlamaBaseTool):
    """Tool for fetching current TVL of a specific DeFi protocol.

    This tool fetches the current Total Value Locked (TVL) for a given protocol
    using the DeFiLlama API. It includes rate limiting to avoid API abuse.

    Example:
        tvl_tool = DefiLlamaFetchProtocolCurrentTvl(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await tvl_tool._arun(protocol="aave")
    """

    name: str = "defillama_fetch_protocol_tvl"
    description: str = FETCH_TVL_PROMPT
    args_schema: Type[BaseModel] = FetchProtocolCurrentTVLInput

    async def _arun(self, protocol: str) -> FetchProtocolCurrentTVLResponse:
        """Fetch current TVL for the given protocol.

        Args:
            config: Runnable configuration
            protocol: DeFi protocol slug (e.g., "aave", "curve")

        Returns:
            FetchProtocolCurrentTVLResponse containing protocol name, TVL value or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchProtocolCurrentTVLResponse(
                    protocol=protocol, tvl=0, error=error_msg
                )

            # Normalize protocol slug
            normalized_protocol = protocol.lower().replace(" ", "-")

            # Fetch TVL from API
            result = await fetch_protocol_current_tvl(normalized_protocol)

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchProtocolCurrentTVLResponse(
                    protocol=normalized_protocol, tvl=0, error=result["error"]
                )

            return FetchProtocolCurrentTVLResponse(
                protocol=normalized_protocol, tvl=float(result)
            )

        except Exception as e:
            return FetchProtocolCurrentTVLResponse(
                protocol=protocol, tvl=0, error=str(e)
            )
