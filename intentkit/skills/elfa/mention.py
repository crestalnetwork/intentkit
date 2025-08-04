"""Mention-related skills for Elfa AI API."""

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from .base import ElfaBaseTool
from .utils import MentionData, make_elfa_request


class ElfaGetTopMentionsInput(BaseModel):
    """Input parameters for top mentions."""

    ticker: str = Field(description="Stock ticker symbol (e.g., ETH, $ETH, BTC, $BTC)")
    timeWindow: Optional[str] = Field(
        "1h", description="Time window (e.g., '1h', '24h', '7d')"
    )
    page: Optional[int] = Field(1, description="Page number for pagination")
    pageSize: Optional[int] = Field(10, description="Number of items per page")


class ElfaGetTopMentionsOutput(BaseModel):
    """Output structure for top mentions response."""

    success: bool
    data: Optional[List[MentionData]] = Field(None, description="List of top mentions")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Response metadata")


class ElfaGetTopMentions(ElfaBaseTool):
    """
    Get top mentions for a specific ticker.

    This tool uses the Elfa API to query tweets mentioning a specific stock ticker.
    The tweets are ranked by view count, providing insight into the most visible and
    potentially influential discussions surrounding the stock. Results are updated hourly.

    Use Cases:
    - Real-time sentiment analysis: Track changes in public opinion about a stock
    - News monitoring: Identify trending news and discussions related to a specific ticker
    - Investor insights: Monitor conversations and opinions of investors and traders
    """

    name: str = "elfa_get_top_mentions"
    description: str = """Get top mentions for a specific ticker symbol ranked by view count. 
    Updated hourly. Returns engagement metrics and account information for market sentiment analysis.
    
    Use this to track public opinion, identify trending news, and monitor investor discussions."""
    args_schema: Type[BaseModel] = ElfaGetTopMentionsInput

    async def _arun(
        self,
        ticker: str,
        timeWindow: str = "1h",
        page: int = 1,
        pageSize: int = 10,
        **kwargs,
    ) -> ElfaGetTopMentionsOutput:
        """
        Execute the top mentions request.

        Args:
            ticker: Stock ticker symbol
            timeWindow: Time window for mentions (default: 1h)
            page: Page number for pagination (default: 1)
            pageSize: Items per page (default: 10)
            config: LangChain runnable configuration
            **kwargs: Additional parameters

        Returns:
            ElfaGetTopMentionsOutput: Structured response with top mentions

        Raises:
            ValueError: If API key is not found
            ToolException: If there's an error with the API request
        """
        api_key = self.get_api_key()

        # Prepare parameters according to API spec
        params = {
            "ticker": ticker,
            "timeWindow": timeWindow,
            "page": page,
            "pageSize": pageSize,
        }

        # Make API request using shared utility
        response = await make_elfa_request(
            endpoint="data/top-mentions", api_key=api_key, params=params
        )

        # Parse response data into MentionData objects
        mentions = []
        if response.data and isinstance(response.data, list):
            mentions = [MentionData(**item) for item in response.data]

        return ElfaGetTopMentionsOutput(
            success=response.success, data=mentions, metadata=response.metadata
        )


class ElfaSearchMentionsInput(BaseModel):
    """Input parameters for search mentions."""

    keywords: Optional[str] = Field(
        None,
        description="Up to 5 keywords to search for, separated by commas. Phrases accepted",
    )
    accountName: Optional[str] = Field(
        None,
        description="Account username to filter by (optional if keywords provided)",
    )
    timeWindow: Optional[str] = Field("7d", description="Time window for search")
    limit: Optional[int] = Field(20, description="Number of results to return (max 30)")
    searchType: Optional[str] = Field(
        "or", description="Type of search ('and' or 'or')"
    )
    cursor: Optional[str] = Field(None, description="Cursor for pagination")


class ElfaSearchMentionsOutput(BaseModel):
    """Output structure for search mentions response."""

    success: bool
    data: Optional[List[MentionData]] = Field(
        None, description="List of matching mentions"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Response metadata with cursor"
    )


class ElfaSearchMentions(ElfaBaseTool):
    """
    Search mentions by keywords or account name.

    This tool uses the Elfa API to search tweets mentioning up to five keywords or from specific accounts.
    It can search within the past 30 days of data (updated every 5 minutes) or access historical data.
    Returns sanitized engagement metrics and sentiment data.

    Use Cases:
    - Market research: Track conversations and sentiment around specific products or industries
    - Brand monitoring: Monitor mentions of your brand and identify potential PR issues
    - Public opinion tracking: Analyze public opinion on various topics
    - Competitive analysis: See what people are saying about your competitors
    """

    name: str = "elfa_search_mentions"
    description: str = """Search tweets by keywords or account name with engagement data and sentiment analysis. 
    Updated every 5 minutes. Access 30 days of recent data or historical archives.
    
    Use this for market research, brand monitoring, opinion tracking, and competitive analysis."""
    args_schema: Type[BaseModel] = ElfaSearchMentionsInput

    async def _arun(
        self,
        keywords: Optional[str] = None,
        accountName: Optional[str] = None,
        timeWindow: str = "7d",
        limit: int = 20,
        searchType: str = "or",
        cursor: Optional[str] = None,
        **kwargs,
    ) -> ElfaSearchMentionsOutput:
        """
        Execute the search mentions request.

        Args:
            keywords: Keywords to search for (optional if accountName provided)
            accountName: Account username to filter by (optional if keywords provided)
            timeWindow: Time window for search (default: 7d)
            limit: Number of results to return (default: 20, max 30)
            searchType: Type of search - 'and' or 'or' (default: 'or')
            cursor: Pagination cursor (optional)
            config: LangChain runnable configuration
            **kwargs: Additional parameters

        Returns:
            ElfaSearchMentionsOutput: Structured response with matching mentions

        Raises:
            ValueError: If API key is not found or neither keywords nor accountName provided
            ToolException: If there's an error with the API request
        """
        api_key = self.get_api_key()

        # Validate that at least one search criteria is provided
        if not keywords and not accountName:
            raise ValueError("Either keywords or accountName must be provided")

        # Prepare parameters according to API spec
        params = {
            "timeWindow": timeWindow,
            "limit": min(limit, 30),  # API max is 30
            "searchType": searchType,
        }

        # Add optional parameters
        if keywords:
            params["keywords"] = keywords
        if accountName:
            params["accountName"] = accountName
        if cursor:
            params["cursor"] = cursor

        # Make API request using shared utility
        response = await make_elfa_request(
            endpoint="data/keyword-mentions", api_key=api_key, params=params
        )

        # Parse response data into MentionData objects
        mentions = []
        if response.data and isinstance(response.data, list):
            mentions = [MentionData(**item) for item in response.data]

        return ElfaSearchMentionsOutput(
            success=response.success, data=mentions, metadata=response.metadata
        )
