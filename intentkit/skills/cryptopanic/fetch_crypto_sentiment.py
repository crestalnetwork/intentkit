"""Skill to provide AI-driven insights on crypto market conditions using CryptoPanic news."""

from typing import ClassVar

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.cryptopanic.base import CryptopanicBaseTool

SUPPORTED_CURRENCIES = ["BTC", "ETH"]


class CryptopanicSentimentInput(BaseModel):
    """Input schema for fetching crypto market insights."""

    currency: str = Field(default="BTC", description="BTC or ETH")


class CryptopanicSentimentOutput(BaseModel):
    """Output schema for crypto market insights."""

    currency: str
    total_posts: int
    headlines: list[str]
    prompt: str
    summary: str


class CryptopanicNewsOutput(BaseModel):
    """Output schema for fetching crypto news (used internally)."""

    currency: str
    news_items: list[BaseModel]
    summary: str


class FetchCryptoSentiment(CryptopanicBaseTool):
    """Skill to provide AI-driven insights on crypto market conditions using CryptoPanic news."""

    name: str = "fetch_crypto_sentiment"
    description: str = "Provides AI-driven market sentiment analysis for BTC or ETH based on recent news."
    args_schema: ArgsSchema | None = CryptopanicSentimentInput

    INSIGHTS_PROMPT: ClassVar[str] = """
{currency} Headlines ({total_posts} posts):
{headlines}

Analyze these headlines for {currency}. Summarize trends, opportunities, and risks. Classify outlook as Bullish/Bearish with buy/sell/hold opinion. Provide concise analysis without headings.
    """

    async def _arun(
        self,
        currency: str = "BTC",
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
        from langchain_core.tools.base import ToolException

        from intentkit.skills.cryptopanic.fetch_crypto_news import (
            FetchCryptoNews,
        )  # Import here to avoid circular import

        currency = currency.upper() if currency else "BTC"
        if currency not in SUPPORTED_CURRENCIES:
            currency = "BTC"

        # Instantiate FetchCryptoNews
        news_skill = FetchCryptoNews()

        try:
            news_output: CryptopanicNewsOutput = await news_skill._arun(  # pyright: ignore[reportPrivateUsage]
                query=f"insights for {currency}",
                currency=currency,
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
