import logging
from decimal import Decimal
from typing import Any, cast

from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field

from intentkit.clients import get_twitter_client
from intentkit.skills.twitter.base import TwitterBaseTool

NAME = "twitter_like_tweet"
PROMPT = "Like a tweet on Twitter"

logger = logging.getLogger(__name__)


class TwitterLikeTweetInput(BaseModel):
    """Input for TwitterLikeTweet tool."""

    tweet_id: str = Field(description="Tweet ID to like")


class TwitterLikeTweet(TwitterBaseTool):
    """Like a tweet on Twitter."""

    name: str = NAME
    description: str = PROMPT
    price: Decimal = Decimal("60")
    args_schema: ArgsSchema | None = TwitterLikeTweetInput

    async def _arun(self, tweet_id: str, **kwargs):
        context = self.get_context()
        try:
            skill_config = context.agent.skill_config(self.category)
            twitter = get_twitter_client(
                agent_id=context.agent_id,
                config=skill_config,
            )
            client = await twitter.get_client()

            # Check rate limit only when not using OAuth
            if not twitter.use_key:
                await self.check_rate_limit(max_requests=100, interval=1440)

            # Like the tweet using tweepy client
            response = cast(
                dict[str, Any],
                await client.like(tweet_id=tweet_id, user_auth=twitter.use_key),
            )

            if "data" in response and "liked" in response["data"]:
                return response
            else:
                logger.error("Error liking tweet: %s", response)
                raise ToolException("Failed to like tweet.")

        except Exception as e:
            logger.error("Error liking tweet: %s", e)
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
