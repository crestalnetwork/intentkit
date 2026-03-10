import logging
from decimal import Decimal

from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field

from intentkit.clients import get_twitter_client
from intentkit.skills.twitter.base import TwitterBaseTool

NAME = "twitter_follow_user"
PROMPT = "Follow a Twitter user by user ID. Use twitter_get_user_by_username to get the ID if needed."
logger = logging.getLogger(__name__)


class TwitterFollowUserInput(BaseModel):
    """Input for TwitterFollowUser tool."""

    user_id: str = Field(description="User ID to follow")


class TwitterFollowUser(TwitterBaseTool):
    """Follow a Twitter user."""

    name: str = NAME
    description: str = PROMPT
    price: Decimal = Decimal("60")
    args_schema: ArgsSchema | None = TwitterFollowUserInput

    async def _arun(self, user_id: str, **kwargs) -> bool:
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
                await self.check_rate_limit(max_requests=5, interval=15)

            # Follow the user using tweepy client
            response = await client.follow_user(
                target_user_id=user_id, user_auth=twitter.use_key
            )

            if "data" in response and response["data"].get("following"):
                return response
            else:
                logger.error(f"Error following user: {str(response)}")
                raise ToolException("Failed to follow user")

        except Exception as e:
            logger.error("Error following user: %s", str(e))
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
