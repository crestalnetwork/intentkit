"""Trending tokens skill for Elfa AI API."""

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from .base import ElfaBaseTool
from .utils import make_elfa_request


class ElfaGetTrendingTokensInput(BaseModel):
    """Input parameters for trending tokens."""

    timeWindow: Optional[str] = Field(
        "7d",
        description="Time window for trending analysis (e.g., '30m', '1h', '4h', '24h', '7d', '30d')",
    )
    page: Optional[int] = Field(1, description="Page number for pagination")
    pageSize: Optional[int] = Field(50, description="Number of items per page")
    minMentions: Optional[int] = Field(
        5, description="Minimum number of mentions required"
    )


class TrendingToken(BaseModel):
    """Individual trending token data."""

    token: Optional[str] = Field(None, description="Token symbol")
    current_count: Optional[int] = Field(None, description="Current mention count")
    previous_count: Optional[int] = Field(None, description="Previous mention count")
    change_percent: Optional[float] = Field(None, description="Change percentage")


class ElfaGetTrendingTokensOutput(BaseModel):
    """Output structure for trending tokens response."""

    success: bool
    data: Optional[List[TrendingToken]] = Field(
        None, description="List of trending tokens"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Response metadata")


class ElfaGetTrendingTokens(ElfaBaseTool):
    """
    Get trending tokens based on smart mentions count.

    This tool ranks the most discussed tokens based on smart mentions count for a given period,
    with updates every 5 minutes via the Elfa API. Smart mentions provide a more sophisticated
    measure of discussion volume than simple keyword counts.

    Use Cases:
    - Identify trending tokens: Quickly see which tokens are gaining traction in online discussions
    - Gauge market sentiment: Track changes in smart mention counts to understand shifts in market opinion
    - Research potential investments: Use the ranking as a starting point for further due diligence
    """

    name: str = "elfa_get_trending_tokens"
    description: str = """Get trending tokens ranked by smart mentions count for a given time period. 
    Updated every 5 minutes. Smart mentions provide sophisticated discussion volume measurement beyond simple keyword counts.
    
    Use this to identify tokens gaining traction, gauge market sentiment, and research potential investments."""
    args_schema: Type[BaseModel] = ElfaGetTrendingTokensInput

    async def _arun(
        self,
        timeWindow: str = "7d",
        page: int = 1,
        pageSize: int = 50,
        minMentions: int = 5,
        **kwargs,
    ) -> ElfaGetTrendingTokensOutput:
        """
        Execute the trending tokens request.

        Args:
            timeWindow: Time window for analysis (default: 7d)
            page: Page number for pagination (default: 1)
            pageSize: Items per page (default: 50)
            minMentions: Minimum mentions required (default: 5)
            config: LangChain runnable configuration
            **kwargs: Additional parameters

        Returns:
            ElfaGetTrendingTokensOutput: Structured response with trending tokens

        Raises:
            ValueError: If API key is not found
            ToolException: If there's an error with the API request
        """
        api_key = self.get_api_key()

        # Prepare parameters according to API spec
        params = {
            "timeWindow": timeWindow,
            "page": page,
            "pageSize": pageSize,
            "minMentions": minMentions,
        }

        # Make API request using shared utility
        response = await make_elfa_request(
            endpoint="aggregations/trending-tokens", api_key=api_key, params=params
        )

        # Parse response data into TrendingToken objects
        trending_tokens = []
        if response.data:
            if isinstance(response.data, list):
                trending_tokens = [TrendingToken(**item) for item in response.data]
            elif isinstance(response.data, dict) and "data" in response.data:
                # Handle nested data structure if present
                trending_tokens = [
                    TrendingToken(**item) for item in response.data["data"]
                ]

        return ElfaGetTrendingTokensOutput(
            success=response.success, data=trending_tokens, metadata=response.metadata
        )
