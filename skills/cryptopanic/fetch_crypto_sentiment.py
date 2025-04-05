"""CryptoPanic market sentiment analysis skill."""

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

# improve filter usage

FILTERS = ["rising", "hot", "bullish", "bearish", "important", "saved", "lol"]

class CryptopanicSentimentInput(BaseModel):
    currency: str = Field(description="Cryptocurrency (e.g., 'BTC')", default="BTC")
    filter: Literal["rising", "hot", "bullish", "bearish", "important", "saved", "lol"] = Field(
        description="Filter (tool uses all filters)", default="rising"
    )

class FilterSentiment(BaseModel):
    filter: str = Field(description="Filter name")
    total_posts: int = Field(description="Number of posts")
    bullish_percentage: float = Field(description="Bullish sentiment percentage")
    bearish_percentage: float = Field(description="Bearish sentiment percentage")
    neutral_percentage: float = Field(description="Neutral sentiment percentage")
    avg_positive_votes: float = Field(description="Average positive votes")
    avg_negative_votes: float = Field(description="Average negative votes")
    headlines: list[str] = Field(description="Headlines")

class CryptopanicSentimentOutput(BaseModel):
    currency: str = Field(description="Queried cryptocurrency")
    filter_data: List[FilterSentiment] = Field(description="Per-filter sentiment data")
    aggregated: FilterSentiment = Field(description="Aggregated sentiment")

class FetchCryptoSentiment(CryptopanicBaseTool):
    name: str = "fetch_crypto_sentiment"
    description: str = """
        Fetches market sentiment from CryptoPanic across all filters (rising, hot, bullish, bearish,
        important, saved, lol). Returns sentiment percentages, vote intensities, headlines, and an
        aggregated summary. Triggers for sentiment, trends, or feelings queries (e.g., 'What’s the
        market sentiment for BTC?').
        """
    args_schema: Type[BaseModel] = CryptopanicSentimentInput

    def _run(self, question: str) -> CryptopanicSentimentOutput:
        raise NotImplementedError("Use _arun for async execution")

    async def fetch_filter_data(self, currency: str, filter: str, api_key: str) -> FilterSentiment:
        url = base_url
        params = {"auth_token": api_key, "public": "true", "currencies": currency.upper(), "filter": filter}
        logger.debug(f"Fetching {filter} data: {params}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()["results"]
                logger.info(f"Got {len(data)} posts for {filter}")

                total_posts = len(data)
                if total_posts == 0:
                    return FilterSentiment(
                        filter=filter, total_posts=0, bullish_percentage=0.0, bearish_percentage=0.0, # new logic req
                        neutral_percentage=0.0, avg_positive_votes=0.0, avg_negative_votes=0.0, headlines=[]
                    )
# rework needed for sentiment analysis 
                total_positive = sum(post["votes"]["positive"] for post in data)
                total_negative = sum(post["votes"]["negative"] for post in data)
                total_votes = total_positive + total_negative
                bullish_posts = sum(1 for post in data if post["votes"]["positive"] > post["votes"]["negative"])
                bearish_posts = sum(1 for post in data if post["votes"]["negative"] > post["votes"]["positive"])
                neutral_posts = total_posts - (bullish_posts + bearish_posts)
                headlines = [post["title"] for post in data]

                return FilterSentiment(
                    filter=filter, total_posts=total_posts,
                    bullish_percentage=(total_positive / total_votes * 100) if total_votes > 0 else 0.0,
                    bearish_percentage=(total_negative / total_votes * 100) if total_votes > 0 else 0.0,
                    neutral_percentage=(neutral_posts / total_posts * 100) if total_posts > 0 else 0.0,
                    avg_positive_votes=(total_positive / total_posts) if total_posts > 0 else 0.0,
                    avg_negative_votes=(total_negative / total_posts) if total_posts > 0 else 0.0,
                    headlines=headlines
                )
            except Exception as e:
                logger.error(f"Error with {filter}: {e}")
                return FilterSentiment(
                    filter=filter, total_posts=0, bullish_percentage=0.0, bearish_percentage=0.0,
                    neutral_percentage=0.0, avg_positive_votes=0.0, avg_negative_votes=0.0, headlines=[]
                )

    async def _arun(
    self, currency: str, filter: str = "hot", config: RunnableConfig = None, **kwargs
) -> CryptopanicSentimentOutput:
    logger.info(f"Fetching sentiment for {currency}")
    context = kwargs.get("context")
    if not context:
        raise ToolException("Context not provided")
    api_key = self.get_api_key(context)
    if not api_key:
        raise ToolException("Missing API key in skill config")

    tasks = [self.fetch_filter_data(currency, f, api_key) for f in FILTERS]
    filter_results = await asyncio.gather(*tasks)

    total_posts_agg = sum(r.total_posts for r in filter_results)
    total_positive_agg = sum(r.avg_positive_votes * r.total_posts for r in filter_results)
    total_negative_agg = sum(r.avg_negative_votes * r.total_posts for r in filter_results)
    total_votes_agg = total_positive_agg + total_negative_agg
    bullish_posts_agg = sum(r.total_posts * (r.bullish_percentage / 100) for r in filter_results if r.total_posts > 0)
    bearish_posts_agg = sum(r.total_posts * (r.bearish_percentage / 100) for r in filter_results if r.total_posts > 0)
    neutral_posts_agg = total_posts_agg - (bullish_posts_agg + bearish_posts_agg)
    all_headlines = [headline for r in filter_results for headline in r.headlines]

    aggregated = FilterSentiment(
        filter="aggregated", total_posts=total_posts_agg,
        bullish_percentage=(total_positive_agg / total_votes_agg * 100) if total_votes_agg > 0 else 0.0,
        bearish_percentage=(total_negative_agg / total_votes_agg * 100) if total_votes_agg > 0 else 0.0,
        neutral_percentage=(neutral_posts_agg / total_posts_agg * 100) if total_posts_agg > 0 else 0.0,
        avg_positive_votes=(total_positive_agg / total_posts_agg) if total_posts_agg > 0 else 0.0,
        avg_negative_votes=(total_negative_agg / total_posts_agg) if total_posts_agg > 0 else 0.0,
        headlines=all_headlines
    )

    return CryptopanicSentimentOutput(currency=currency, filter_data=filter_results, aggregated=aggregated)
