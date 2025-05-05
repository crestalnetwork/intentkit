import logging
from typing import Type

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from clients.twitter import get_twitter_client
from skills.twitter.base import TwitterBaseTool

NAME = "twitter_like_tweet"
PROMPT = "Like a tweet on Twitter"

logger = logging.getLogger(__name__)


class TwitterLikeTweetInput(BaseModel):
    """Input for TwitterLikeTweet tool."""

    tweet_id: str = Field(description="The ID of the tweet to like")


class TwitterLikeTweet(TwitterBaseTool):
    """Tool for liking tweets on Twitter.

    This tool uses the Twitter API v2 to like tweets on Twitter.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = TwitterLikeTweetInput

    async def _arun(self, tweet_id: str, config: RunnableConfig, **kwargs) -> bool:
        """Async implementation of the tool to like a tweet.

        Args:
            tweet_id (str): The ID of the tweet to like.
            config (RunnableConfig): The configuration for the runnable, containing agent context.

        Returns:
            bool: True if the tweet was successfully liked.

        Raises:
            Exception: If there's an error accessing the Twitter API or liking the tweet.
        """
        try:
            context = self.context_from_config(config)
            twitter = get_twitter_client(
                agent_id=context.agent.id,
                skill_store=self.skill_store,
                config=context.config,
            )
            client = await twitter.get_client()

            # Check rate limit only when not using OAuth
            if not twitter.use_key:
                await self.check_rate_limit(
                    context.agent.id, max_requests=100, interval=1440
                )

            # Like the tweet using tweepy client
            response = await client.like(tweet_id=tweet_id, user_auth=twitter.use_key)

            if "data" in response and "liked" in response["data"]:
                return response
            else:
                logger.error(f"Error liking tweet: {str(response)}")
                raise ToolException("Failed to like tweet.")

        except Exception as e:
            logger.error(f"Error liking tweet: {str(e)}")
            raise type(e)(f"[agent:{context.agent.id}]: {e}") from e
