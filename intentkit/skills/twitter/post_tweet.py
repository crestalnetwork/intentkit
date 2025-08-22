import logging
from typing import Optional, Type

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from intentkit.clients import get_twitter_client
from intentkit.skills.twitter.base import TwitterBaseTool

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
        **kwargs,
    ):
        context = self.get_context()
        try:
            skill_config = context.agent.skill_config(self.category)
            twitter = get_twitter_client(
                agent_id=context.agent_id,
                skill_store=self.skill_store,
                config=skill_config,
            )
            client = await twitter.get_client()

            # Check rate limit only when not using OAuth
            if not twitter.use_key:
                await self.check_rate_limit(
                    context.agent_id, max_requests=24, interval=1440
                )

            media_ids = []
            image_warning = ""

            # Handle image upload if provided
            if image:
                # Validate image URL - must be from system's S3 CDN
                aws_s3_cdn_url = await self.skill_store.get_system_config(
                    "aws_s3_cdn_url"
                )
                if aws_s3_cdn_url and image.startswith(aws_s3_cdn_url):
                    # Use the TwitterClient method to upload the image
                    media_ids = await twitter.upload_media(context.agent_id, image)
                else:
                    # Image is not from system's S3 CDN, skip upload but warn
                    image_warning = "Warning: The provided image URL is not from the system's S3 CDN and has been ignored. "
                    logger.warning(
                        f"Image URL validation failed for agent {context.agent_id}: {image}"
                    )

            # Post tweet using tweepy client
            tweet_params = {"text": text, "user_auth": twitter.use_key}
            if media_ids:
                tweet_params["media_ids"] = media_ids

            response = await client.create_tweet(**tweet_params)
            if "data" in response and "id" in response["data"]:
                # Return response with warning if image was ignored
                result = (
                    f"{image_warning}Tweet posted successfully. Response: {response}"
                )
                return result
            else:
                logger.error(f"Error posting tweet: {str(response)}")
                raise ToolException("Failed to post tweet.")

        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
