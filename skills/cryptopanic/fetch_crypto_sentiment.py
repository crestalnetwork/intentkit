"""Skill to provide AI-driven insights on crypto market conditions using CryptoPanic news."""

from typing import ClassVar, List, Type

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from skills.cryptopanic.base import CryptopanicBaseTool

SUPPORTED_CURRENCIES = ["BTC", "ETH"]


class CryptopanicSentimentInput(BaseModel):
    """Input schema for fetching crypto market insights."""

    currency: str = Field(default="BTC", description="Currency to analyze (BTC or ETH)")


class CryptopanicSentimentOutput(BaseModel):
    """Output schema for crypto market insights."""

    currency: str = Field(description="Currency analyzed")
    total_posts: int = Field(description="Number of news items analyzed")
    headlines: list[str] = Field(description="List of news headlines")
    prompt: str = Field(description="Formatted prompt for LLM insights")
    summary: str = Field(description="Summary of analysis process")


class CryptopanicNewsOutput(BaseModel):
    """Output schema for fetching crypto news (used internally)."""

    currency: str = Field(description="Currency news was fetched for")
    news_items: List[BaseModel] = Field(description="List of news items")
    summary: str = Field(description="Summary of fetched news")


class FetchCryptoSentiment(CryptopanicBaseTool):
    """Skill to provide AI-driven insights on crypto market conditions using CryptoPanic news."""

    name: str = "fetch_crypto_sentiment"
    description: str = (
        "Provides AI-driven insights on market conditions for BTC or ETH, including trends, "
        "opportunities, risks, and outlook, based on news fetched from fetch_crypto_news "
        "with all posts sorted by recency. Triggered by 'sentiment' or 'market state' queries. "
        "Defaults to BTC."
    )
    args_schema: Type[BaseModel] = CryptopanicSentimentInput
    skill_store: SkillStoreABC = Field(description="Skill store for data persistence")

    INSIGHTS_PROMPT: ClassVar[str] = """
CryptoPanic Headlines for {currency}:
{headlines}

Total Posts: {total_posts}
Currency: {currency}

Based on these headlines, provide AI-driven insights into the market conditions for {currency}. 
Summarize key trends (e.g., price movements, adoption, network developments) inferred from the news. 
Identify significant opportunities (e.g., growth potential) and risks (e.g., negative sentiment, competition). 
Classify the overall market outlook as Bullish, Bearish and provide opinion on wether to buy, sell or hold.
Conclude with a short-term outlook for {currency}. Provide a concise, professional analysis without headings.
    """

    async def _arun(
        self,
        currency: str = "BTC",
        config: RunnableConfig = None,
        **kwargs,
    ) -> CryptopanicSentimentOutput:
        """Generate AI-driven market insights asynchronously.

        Args:
            currency: Currency to analyze (defaults to BTC).
            config: Runnable configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            CryptopanicSentimentOutput with market insights.

        Raises:
            ToolException: If news fetching fails.
        """
        from langchain.tools.base import ToolException

        from skills.cryptopanic.fetch_crypto_news import (
            FetchCryptoNews,
        )  # Import here to avoid circular import

        currency = currency.upper() if currency else "BTC"
        if currency not in SUPPORTED_CURRENCIES:
            currency = "BTC"

        # Instantiate FetchCryptoNews
        news_skill = FetchCryptoNews(skill_store=self.skill_store)

        try:
            news_output: CryptopanicNewsOutput = await news_skill._arun(
                query=f"insights for {currency}",
                currency=currency,
                config=config,
            )
        except Exception as e:
            raise ToolException(f"Failed to fetch news for analysis: {e}")

        news_items = news_output.news_items
        total_posts = len(news_items)

        if total_posts == 0:
            headlines = ["No recent news available"]
            summary = f"No news found for {currency} to analyze."
        else:
            headlines = [item.title for item in news_items[:5]]  # Limit to 5
            summary = f"Generated insights for {currency} based on {total_posts} news items sorted by recency."

        # Format headlines as numbered list
        formatted_headlines = "\n".join(
            f"{i + 1}. {headline}" for i, headline in enumerate(headlines)
        )

        prompt = self.INSIGHTS_PROMPT.format(
            total_posts=total_posts,
            currency=currency,
            headlines=formatted_headlines,
        )

        return CryptopanicSentimentOutput(
            currency=currency,
            total_posts=total_posts,
            headlines=headlines,
            prompt=prompt,
            summary=summary,
        )

    def _run(self, question: str):
        raise NotImplementedError("Use _arun for async execution")
