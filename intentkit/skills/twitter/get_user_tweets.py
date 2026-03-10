import logging
from decimal import Decimal

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.clients import get_twitter_client

from .base import TwitterBaseTool

logger = logging.getLogger(__name__)

NAME = "twitter_get_user_tweets"
PROMPT = (
    "Get tweets from a specific user by user ID. If result_count is 0, don't retry."
)


class TwitterGetUserTweetsInput(BaseModel):
    """Input for TwitterGetUserTweets tool."""

    user_id: str = Field(description="Twitter user ID")
    exclude: list[str] | None = Field(
        default=["replies", "retweets"],
        description="Tweet types to exclude: 'replies', 'retweets'",
    )


class TwitterGetUserTweets(TwitterBaseTool):
    """Get tweets from a specific Twitter user."""

    name: str = NAME
    description: str = PROMPT
    price: Decimal = Decimal("60")
    args_schema: ArgsSchema | None = TwitterGetUserTweetsInput

    async def _arun(self, **kwargs):
        context = self.get_context()
        try:
            user_id = kwargs.get("user_id")
            if not user_id:
                raise ToolException("User ID is required")

            # Hardcode max_results to 10
            max_results = 10

            # Get exclude parameter with default
            exclude = kwargs.get("exclude", ["replies", "retweets"])

            skill_config = context.agent.skill_config(self.category)
            twitter = get_twitter_client(
                agent_id=context.agent_id,
                config=skill_config,
            )
            client = await twitter.get_client()

            # Check rate limit only when not using OAuth
            if not twitter.use_key:
                await self.check_rate_limit(max_requests=1, interval=15)

            # get since id from store
            last = await self.get_agent_skill_data(user_id)
            last = last or {}
            since_id = last.get("since_id")

            tweets = await client.get_users_tweets(
                user_auth=twitter.use_key,
                id=user_id,
                max_results=max_results,
                since_id=since_id,
                exclude=exclude,
                expansions=[
                    "referenced_tweets.id",
                    "referenced_tweets.id.attachments.media_keys",
                    "referenced_tweets.id.author_id",
                    "attachments.media_keys",
                    "author_id",
                ],
                tweet_fields=[
                    "created_at",
                    "author_id",
                    "text",
                    "referenced_tweets",
                    "attachments",
                ],
                user_fields=[
                    "username",
                    "name",
                    "profile_image_url",
                    "description",
                    "public_metrics",
                    "location",
                    "connection_status",
                ],
                media_fields=["url", "type", "width", "height"],
            )

            # Update the since_id in store for the next request
            if tweets.get("meta") and tweets["meta"].get("newest_id"):
                last["since_id"] = tweets["meta"]["newest_id"]
                await self.save_agent_skill_data(user_id, last)

            return tweets

        except Exception as e:
            logger.error("Error getting user tweets: %s", str(e))
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
