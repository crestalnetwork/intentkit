"""CryptoPanic latest market news skill."""

from typing import Literal, Type, List
import httpx
import logging
import os
import asyncio
from langchain.tools.base import ToolException
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.cryptopanic.base import CryptopanicBaseTool, base_url

logger = logging.getLogger(__name__)

FILTERS = ["rising", "hot", "bullish", "bearish", "important", "saved", "lol"]

class CryptopanicNewsInput(BaseModel):
    currency: str = Field(description="Cryptocurrency (e.g., 'BTC') or 'all'", default="all")
    filter: Literal["rising", "hot", "bullish", "bearish", "important", "saved", "lol"] = Field(
        description="Filter (tool uses all filters)", default="hot"
    )

class NewsItem(BaseModel):
    title: str = Field(description="News headline")
    published_at: str = Field(description="Publication date (ISO)")
    source: str = Field(description="News source or 'CryptoPanic'")
    filter: str = Field(description="Filter category")

class CryptopanicNewsOutput(BaseModel):
    currency: str = Field(description="Queried cryptocurrency")
    news_items: List[NewsItem] = Field(description="Recent news items")
    summary: str = Field(description="Summary of trends")

# add content to desc

class FetchCryptoNews(CryptopanicBaseTool):
    name: str = "fetch_crypto_news"
    description: str = """
        Fetches latest crypto market news from CryptoPanic across all filters (rising, hot, bullish,
        bearish, important, saved, lol). Returns headlines, dates, sources, and a summary. Triggers
        for news or update queries (e.g., 'What’s the latest crypto news?', 'Any market updates?').
        """
    args_schema: Type[BaseModel] = CryptopanicNewsInput

    def _run(self, question: str) -> CryptopanicNewsOutput:
        raise NotImplementedError("Use _arun for async execution")

    async def fetch_filter_news(self, currency: str, filter: str, api_key: str) -> List[NewsItem]:
        url = base_url
        params = {"auth_token": api_key, "public": "true", "filter": filter}
        if currency.lower() != "all":
            params["currencies"] = currency.upper()

        logger.debug(f"Fetching {filter} news: {params}")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()["results"]
                logger.info(f"Got {len(data)} news items for {filter}")

                return [
                    NewsItem(
                        title=post["title"],
                        published_at=post.get("published_at", "Unknown"),
                        source=post.get("source", {}).get("domain", "CryptoPanic"),
                        filter=filter
                    )
                    for post in data
                ]
            except Exception as e:
                logger.error(f"Error with {filter}: {e}")
                return []

    async def _arun(
        self, currency: str, filter: str = "hot", config: RunnableConfig = None, **kwargs
    ) -> CryptopanicSentimentOutput:
        logger.info(f"Fetching sentiment for {currency}")
        context = kwargs.get("context")  # Get context from kwargs
        if not context:
            raise ToolException("Context not provided")
        api_key = self.get_api_key(context)  # Use get_api_key
        if not api_key:
            raise ToolException("Missing API key in skill config")

        tasks = [self.fetch_filter_news(currency, f, api_key) for f in FILTERS]
        filter_results = await asyncio.gather(*tasks)

        all_news_items = [item for sublist in filter_results for item in sublist]
        total_items = len(all_news_items)
        active_filters = sum(1 for r in filter_results if r)

        summary = (
            f"Found {total_items} news items across {active_filters} filters. "
            "Trends: institutional moves, volatility, regulatory updates."
        ) if total_items > 0 else "No news found."

        return CryptopanicNewsOutput(currency=currency, news_items=all_news_items, summary=summary)
