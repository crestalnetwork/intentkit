"""Smart stats skill for Elfa AI API."""

from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field

from .base import ElfaBaseTool
from .utils import SmartStatsData, make_elfa_request


class ElfaGetSmartStatsInput(BaseModel):
    """Input parameters for smart stats."""

    username: str = Field(description="Account username to get stats for")


class ElfaGetSmartStatsOutput(BaseModel):
    """Output structure for smart stats response."""

    success: bool
    data: Optional[SmartStatsData] = Field(None, description="Smart stats data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Response metadata")


class ElfaGetSmartStats(ElfaBaseTool):
    """
    Get smart stats for a specific username.

    This tool uses the Elfa API to retrieve key social media metrics for a given username including:
    - Smart Following Count: Number of high-quality or influential followers
    - Average Engagement: Composite score reflecting interaction with user's content
    - Average Reach: Average reach of the user's content
    - Smart Follower Count: Number of smart followers
    - Follower Count: Total follower count

    Use Cases:
    - Competitor analysis: Compare social media performance to competitors
    - Influencer identification: Identify influential users in your niche
    - Social media audits: Assess overall health and effectiveness of social media presence
    """

    name: str = "elfa_get_smart_stats"
    description: str = """Get comprehensive social media metrics for a username including smart following count, 
    engagement scores, and follower analytics. Use this for competitor analysis, influencer identification, 
    and social media performance audits."""
    args_schema: Type[BaseModel] = ElfaGetSmartStatsInput

    async def _arun(self, username: str, **kwargs) -> ElfaGetSmartStatsOutput:
        """
        Execute the smart stats request.

        Args:
            username: The username to check stats for
            config: LangChain runnable configuration
            **kwargs: Additional parameters

        Returns:
            ElfaGetSmartStatsOutput: Structured response with smart stats

        Raises:
            ValueError: If API key is not found
            ToolException: If there's an error with the API request
        """
        api_key = self.get_api_key()

        # Prepare parameters according to API spec
        params = {"username": username}

        # Make API request using shared utility
        response = await make_elfa_request(
            endpoint="account/smart-stats", api_key=api_key, params=params
        )

        # Parse response data into SmartStatsData object
        stats_data = None
        if response.data and isinstance(response.data, dict):
            stats_data = SmartStatsData(**response.data)

        return ElfaGetSmartStatsOutput(
            success=response.success, data=stats_data, metadata=response.metadata
        )
