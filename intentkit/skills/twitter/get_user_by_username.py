import logging
from typing import Type

from pydantic import BaseModel, Field

from intentkit.clients import get_twitter_client

from .base import TwitterBaseTool

logger = logging.getLogger(__name__)

NAME = "twitter_get_user_by_username"
PROMPT = (
    "Get a Twitter user's information by their username."
    "Returns detailed user information as a json object."
)


class TwitterGetUserByUsernameInput(BaseModel):
    """Input for TwitterGetUserByUsername tool."""

    username: str = Field(description="The Twitter username to lookup")


class TwitterGetUserByUsername(TwitterBaseTool):
    """Tool for getting a Twitter user by their username.

    This tool uses the Twitter API v2 to retrieve user information by username.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = TwitterGetUserByUsernameInput

    async def _arun(self, username: str, **kwargs):
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
                    context.agent_id, max_requests=5, interval=60 * 24
                )

            user_data = await client.get_user(
                username=username,
                user_auth=twitter.use_key,
                user_fields=[
                    "created_at",
                    "description",
                    "entities",
                    "connection_status",
                    "id",
                    "location",
                    "name",
                    "pinned_tweet_id",
                    "profile_image_url",
                    "protected",
                    "public_metrics",
                    "url",
                    "username",
                    "verified",
                    "verified_type",
                    "withheld",
                ],
            )

            return user_data

        except Exception as e:
            logger.error(f"Error getting user by username: {str(e)}")
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
