"""Skill to fetch the latest crypto market news from CryptoPanic API.

Fetches all news posts for BTC or ETH, sorted by publication date (newest first).
"""

from typing import List, Type

import httpx
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.cryptopanic.base import CryptopanicBaseTool

SUPPORTED_CURRENCIES = ["BTC", "ETH"]
BASE_URL = "https://cryptopanic.com/api/v1/posts/"


class CryptopanicNewsInput(BaseModel):
    """Input schema for fetching crypto news."""

    query: str = Field(description="Query to specify currency (e.g., 'btc news')")
    currency: str = Field(
        default="BTC", description="Currency to fetch news for (BTC or ETH)"
    )


class NewsItem(BaseModel):
    """Data model for a single news item."""

    title: str = Field(description="News headline")
    published_at: str = Field(description="Publication timestamp")
    source: str = Field(description="News source domain")


class CryptopanicNewsOutput(BaseModel):
    """Output schema for fetching crypto news."""

    currency: str = Field(description="Currency news was fetched for")
    news_items: List[NewsItem] = Field(description="List of news items")
    summary: str = Field(description="Summary of fetched news")


class FetchCryptoNews(CryptopanicBaseTool):
    """Skill to fetch the latest crypto market news from CryptoPanic API."""

    name: str = "fetch_crypto_news"
    description: str = (
        "Fetches all crypto market news posts from CryptoPanic for BTC or ETH, "
        "sorted by publication date (newest first). Defaults to BTC."
    )
    args_schema: Type[BaseModel] = CryptopanicNewsInput
    skill_store: SkillStoreABC = Field(description="Skill store for data persistence")

    async def fetch_news(
        self,
        currency: str,
        api_key: str,
    ) -> List[NewsItem]:
        """Fetch the latest news for a specific currency from CryptoPanic API.

        Args:
            currency: Currency to fetch news for (BTC or ETH).
            api_key: CryptoPanic API key.

        Returns:
            List of NewsItem objects, sorted by publication date (newest first).

        Raises:
            ToolException: If the API request fails or data is invalid.
        """
        from langchain.tools.base import ToolException

        if currency not in SUPPORTED_CURRENCIES:
            raise ToolException(f"Unsupported currency: {currency}")

        params = {
            "auth_token": api_key,
            "public": "true",
            "currencies": currency.upper(),
            "sort": "-published_at",  # Sort by newest first
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(BASE_URL, params=params, timeout=10)
                response.raise_for_status()
                data = response.json().get("results", [])
                return [
                    NewsItem(
                        title=post["title"],
                        published_at=post.get("published_at", "Unknown"),
                        source=post.get("source", {}).get("domain", "CryptoPanic"),
                    )
                    for post in data
                ]
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                raise ToolException(f"Error fetching news from CryptoPanic: {e}")

    async def _arun(
        self,
        query: str = "",
        currency: str = "BTC",
        **kwargs,
    ) -> CryptopanicNewsOutput:
        """Fetch the latest crypto news asynchronously.

        Args:
            query: Query to specify currency (e.g., 'btc news').
            currency: Currency to fetch news for (defaults to BTC).
            config: Runnable configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            CryptopanicNewsOutput with news items and summary.

        Raises:
            ToolException: If the API key is missing or request fails.
        """

        currency = currency.upper() if currency else "BTC"
        if currency not in SUPPORTED_CURRENCIES:
            currency = "BTC"

        api_key = self.get_api_key()

        news_items = await self.fetch_news(currency, api_key)

        # Deduplicate news items by title
        seen_titles = set()
        unique_news_items = [
            item
            for item in news_items
            if item.title not in seen_titles and not seen_titles.add(item.title)
        ]

        total_items = len(unique_news_items)
        summary = (
            f"Fetched {total_items} unique news posts for {currency}, sorted by recency."
            if unique_news_items
            else f"No news posts found for {currency}."
        )

        return CryptopanicNewsOutput(
            currency=currency,
            news_items=unique_news_items,
            summary=summary,
        )

    def _run(self, question: str):
        raise NotImplementedError("Use _arun for async execution")
