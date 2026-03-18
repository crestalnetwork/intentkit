"""Tool for fetching cryptocurrency news via CryptoCompare API."""

import logging

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.cryptocompare.base import CryptoCompareBaseTool, CryptoNews

logger = logging.getLogger(__name__)


class CryptoCompareFetchNewsInput(BaseModel):
    """Input for CryptoCompareFetchNews tool."""

    token: str = Field(..., description="Token symbol (e.g., BTC, ETH)")


class CryptoCompareFetchNews(CryptoCompareBaseTool):
    """Tool for fetching cryptocurrency news from CryptoCompare."""

    name: str = "cryptocompare_fetch_news"
    description: str = "Fetch latest crypto news for a specific token."
    args_schema: ArgsSchema | None = CryptoCompareFetchNewsInput

    async def _arun(
        self,
        token: str,
        **kwargs,
    ) -> list[CryptoNews]:
        """Async implementation of the tool to fetch cryptocurrency news.

        Args:
            token: Token symbol to fetch news for (e.g., BTC, ETH, SOL)
            config: The configuration for the runnable, containing agent context.

        Returns:
            list[CryptoNews]: A list of cryptocurrency news articles.

        Raises:
            Exception: If there's an error accessing the CryptoCompare API.
        """
        try:
            context = self.get_context()

            # Check rate limit
            await self.check_rate_limit(max_requests=5, interval=60)

            # Get API key from platform config
            api_key = self.get_api_key()

            # Fetch news data directly
            news_data = await self.fetch_news(api_key, token)

            # Check for errors
            if "error" in news_data:
                raise ToolException(news_data["error"])

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
