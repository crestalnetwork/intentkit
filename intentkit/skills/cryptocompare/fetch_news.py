"""Tool for fetching cryptocurrency news via CryptoCompare API."""

import logging
from typing import List, Type

from pydantic import BaseModel, Field

from intentkit.skills.cryptocompare.base import CryptoCompareBaseTool, CryptoNews

logger = logging.getLogger(__name__)


class CryptoCompareFetchNewsInput(BaseModel):
    """Input for CryptoCompareFetchNews tool."""

    token: str = Field(
        ..., description="Token symbol to fetch news for (e.g., BTC, ETH, SOL)"
    )


class CryptoCompareFetchNews(CryptoCompareBaseTool):
    """Tool for fetching cryptocurrency news from CryptoCompare.

    This tool uses the CryptoCompare API to retrieve the latest news articles
    related to a specific cryptocurrency token.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "cryptocompare_fetch_news"
    description: str = "Fetch the latest cryptocurrency news for a specific token"
    args_schema: Type[BaseModel] = CryptoCompareFetchNewsInput

    async def _arun(
        self,
        token: str,
        **kwargs,
    ) -> List[CryptoNews]:
        """Async implementation of the tool to fetch cryptocurrency news.

        Args:
            token: Token symbol to fetch news for (e.g., BTC, ETH, SOL)
            config: The configuration for the runnable, containing agent context.

        Returns:
            List[CryptoNews]: A list of cryptocurrency news articles.

        Raises:
            Exception: If there's an error accessing the CryptoCompare API.
        """
        try:
            context = self.get_context()
            skill_config = context.agent.skill_config(self.category)

            # Check rate limit
            await self.check_rate_limit(context.agent_id, max_requests=5, interval=60)

            # Get API key from context
            api_key = skill_config.get("api_key")
            if not api_key:
                raise ValueError("CryptoCompare API key not found in configuration")

            # Fetch news data directly
            news_data = await self.fetch_news(api_key, token)

            # Check for errors
            if "error" in news_data:
                raise ValueError(news_data["error"])

            # Convert to list of CryptoNews objects
            result = []
            if "Data" in news_data and news_data["Data"]:
                for article in news_data["Data"]:
                    result.append(
                        CryptoNews(
                            id=str(article["id"]),
                            published_on=article["published_on"],
                            title=article["title"],
                            url=article["url"],
                            body=article["body"],
                            tags=article.get("tags", ""),
                            categories=article.get("categories", ""),
                            source=article["source"],
                            source_info=article.get("source_info", {}),
                        )
                    )

            return result

        except Exception as e:
            logger.error("Error fetching news: %s", str(e))
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
