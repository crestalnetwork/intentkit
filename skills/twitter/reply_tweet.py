import logging
from typing import Optional, Type

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from clients.twitter import get_twitter_client
from skills.twitter.base import TwitterBaseTool

NAME = "twitter_reply_tweet"
PROMPT = (
    "Reply to an existing tweet on Twitter. If you want to post image, "
    "you must provide image url in parameters, do not add image link in text."
)

logger = logging.getLogger(__name__)


class TwitterReplyTweetInput(BaseModel):
    """Input for TwitterReplyTweet tool."""

    tweet_id: str = Field(description="The ID of the tweet to reply to")
    text: str = Field(
        description="Tweet text (280 chars for regular users, 25,000 bytes for verified)",
        max_length=25000,
    )
    image: Optional[str] = Field(
        default=None, description="Optional URL of an image to attach to the reply"
    )


class TwitterReplyTweet(TwitterBaseTool):
    """Tool for replying to tweets on Twitter.

    This tool uses the Twitter API v2 to post reply tweets to existing tweets.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = TwitterReplyTweetInput

    async def _arun(
        self,
        tweet_id: str,
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
                    context.agent.id, max_requests=48, interval=1440
                )

            media_ids = []

            # Handle image upload if provided
            if image:
                # Use the TwitterClient method to upload the image
                media_ids = await twitter.upload_media(context.agent.id, image)

            # Post reply tweet using tweepy client
            tweet_params = {
                "text": text,
                "user_auth": twitter.use_key,
                "in_reply_to_tweet_id": tweet_id,
            }

            if media_ids:
                tweet_params["media_ids"] = media_ids

            response = await client.create_tweet(**tweet_params)

            if "data" in response and "id" in response["data"]:
                return response
            else:
                logger.error(f"Error replying to tweet: {str(response)}")
                raise ToolException("Failed to post reply tweet.")

        except Exception as e:
            logger.error(f"Error replying to tweet: {str(e)}")
            raise type(e)(f"[agent:{context.agent.id}]: {e}") from e
