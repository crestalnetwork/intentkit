import logging
from typing import List, Optional, Type

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from clients.twitter import get_twitter_client

from .base import TwitterBaseTool

logger = logging.getLogger(__name__)

NAME = "twitter_get_user_tweets"
PROMPT = (
    "Get tweets from a specific Twitter user by their user ID. "
    "The result is a json object containing a list of tweets."
    'If the result is `{"meta": {"result_count": 0}}`, means no tweets found, don\'t retry this tool.'
)


class TwitterGetUserTweetsInput(BaseModel):
    """Input for TwitterGetUserTweets tool."""

    user_id: str = Field(description="The Twitter user ID to fetch tweets from")
    exclude: Optional[List[str]] = Field(
        default=["replies", "retweets"],
        description="Types of tweets to exclude (e.g., 'replies', 'retweets')",
    )


class TwitterGetUserTweets(TwitterBaseTool):
    """Tool for getting tweets from a specific Twitter user.

    This tool uses the Twitter API v2 to retrieve tweets from a specific user
    by their user ID.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = TwitterGetUserTweetsInput

    async def _arun(self, config: RunnableConfig, **kwargs):
        try:
            user_id = kwargs.get("user_id")
            if not user_id:
                raise ValueError("User ID is required")

            # Hardcode max_results to 10
            max_results = 10

            # Get exclude parameter with default
            exclude = kwargs.get("exclude", ["replies", "retweets"])

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
                    context.agent.id, max_requests=3, interval=60 * 24
                )

            # get since id from store
            last = await self.skill_store.get_agent_skill_data(
                context.agent.id, self.name, user_id
            )
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
                await self.skill_store.save_agent_skill_data(
                    context.agent.id, self.name, user_id, last
                )

            return tweets

        except Exception as e:
            logger.error("Error getting user tweets: %s", str(e))
            raise type(e)(f"[agent:{context.agent.id}]: {e}") from e
