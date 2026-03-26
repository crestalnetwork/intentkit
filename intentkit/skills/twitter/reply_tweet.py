import logging
from decimal import Decimal
from typing import Any, cast

from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field

from intentkit.clients import get_twitter_client
from intentkit.clients.s3 import get_cdn_url
from intentkit.config.config import config
from intentkit.skills.twitter.base import TwitterBaseTool

NAME = "twitter_reply_tweet"
PROMPT = "Reply to a tweet. Do not reply to your own tweets. Use the image parameter for attachments instead of adding links in text."

logger = logging.getLogger(__name__)


class TwitterReplyTweetInput(BaseModel):
    """Input for TwitterReplyTweet tool."""

    tweet_id: str = Field(description="Tweet ID to reply to")
    text: str = Field(
        description="Reply text",
        max_length=25000,
    )
    image: str | None = Field(default=None, description="Image URL to attach")


class TwitterReplyTweet(TwitterBaseTool):
    """Reply to a tweet on Twitter."""

    name: str = NAME
    description: str = PROMPT
    price: Decimal = Decimal("60")
    args_schema: ArgsSchema | None = TwitterReplyTweetInput

    async def _arun(
        self,
        tweet_id: str,
        text: str,
        image: str | None = None,
        **kwargs,
    ):
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
                await self.check_rate_limit(max_requests=48, interval=1440)

            media_ids = []
            image_warning = ""

            # Handle image upload if provided
            if image:
                # Validate image URL - must be from system's S3 CDN.
                # The agent outputs full CDN URLs (skills prepend cdn_url after upload).
                aws_s3_cdn_url = config.aws_s3_cdn_url
                if aws_s3_cdn_url and image.startswith(aws_s3_cdn_url):
                    # Use the TwitterClient method to upload the image
                    media_ids = await twitter.upload_media(context.agent_id, image)
                elif not image.startswith("http") and aws_s3_cdn_url:
                    # Relative path — build full CDN URL before uploading
                    full_url = get_cdn_url(image)
                    media_ids = await twitter.upload_media(context.agent_id, full_url)
                else:
                    # Image is not from system's S3 CDN, skip upload but warn
                    image_warning = "Warning: The provided image URL is not from the system's S3 CDN and has been ignored. "
                    logger.warning(
                        f"Image URL validation failed for agent {context.agent_id}: {image}"
                    )

            # Post reply tweet using tweepy client
            tweet_params: dict[str, Any] = {
                "text": text,
                "user_auth": twitter.use_key,
                "in_reply_to_tweet_id": tweet_id,
            }

            if media_ids:
                tweet_params["media_ids"] = media_ids

            response = cast(
                dict[str, Any],
                await client.create_tweet(**tweet_params),
            )

            if "data" in response and "id" in response["data"]:
                # Return response with warning if image was ignored
                result = f"{image_warning}Reply tweet posted successfully. Response: {response}"
                return result
            else:
                logger.error("Error replying to tweet: %s", response)
                raise ToolException("Failed to post reply tweet.")

        except Exception as e:
            logger.error("Error replying to tweet: %s", e)
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
