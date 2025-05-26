import logging
from typing import Optional, Type

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from clients.twitter import get_twitter_client
from skills.twitter.base import TwitterBaseTool

NAME = "twitter_post_tweet"
PROMPT = (
    "Post a new tweet to Twitter. If you want to post image, "
    "you must provide image url in parameters, do not add image link in text."
)

logger = logging.getLogger(__name__)


class TwitterPostTweetInput(BaseModel):
    """Input for TwitterPostTweet tool."""

    text: str = Field(
        description="Tweet text (280 chars for regular users, 25,000 bytes for verified)",
        max_length=25000,
    )
    image: Optional[str] = Field(
        default=None, description="Optional URL of an image to attach to the tweet"
    )


class TwitterPostTweet(TwitterBaseTool):
    """Tool for posting tweets to Twitter.

    This tool uses the Twitter API v2 to post new tweets to Twitter.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = TwitterPostTweetInput

    async def _arun(
        self,
        text: str,
        image: Optional[str] = None,
        config: RunnableConfig = None,
        **kwargs,
    ):
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
                    context.agent.id, max_requests=24, interval=1440
                )

            media_ids = []

            # Handle image upload if provided
            if image:
                # Use the TwitterClient method to upload the image
                media_ids = await twitter.upload_media(context.agent.id, image)

            # Post tweet using tweepy client
            tweet_params = {"text": text, "user_auth": twitter.use_key}
            if media_ids:
                tweet_params["media_ids"] = media_ids

            response = await client.create_tweet(**tweet_params)
            if "data" in response and "id" in response["data"]:
                return response
            else:
                logger.error(f"Error posting tweet: {str(response)}")
                raise ToolException("Failed to post tweet.")

        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            raise type(e)(f"[agent:{context.agent.id}]: {e}") from e
