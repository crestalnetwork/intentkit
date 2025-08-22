import datetime
import logging
from typing import Type

from pydantic import BaseModel, Field

from intentkit.clients import get_twitter_client

from .base import TwitterBaseTool

logger = logging.getLogger(__name__)

NAME = "twitter_search_tweets"
PROMPT = "Search for recent tweets on Twitter using a query keyword."


class TwitterSearchTweetsInput(BaseModel):
    """Input for TwitterSearchTweets tool."""

    query: str = Field(description="The search query to find tweets")


class TwitterSearchTweets(TwitterBaseTool):
    """Tool for searching recent tweets on Twitter.

    This tool uses the Twitter API v2 to search for recent tweets based on a query.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = TwitterSearchTweetsInput

    async def _arun(self, query: str, **kwargs):
        context = self.get_context()
        max_results = 10
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
                    context.agent_id, max_requests=1, interval=15
                )

            # Get since_id from store to avoid duplicate results
            last = await self.skill_store.get_agent_skill_data(
                context.agent_id, self.name, query
            )
            last = last or {}
            since_id = last.get("since_id")

            # Reset since_id if the saved timestamp is over 6 days old
            if since_id and last.get("timestamp"):
                try:
                    saved_time = datetime.datetime.fromisoformat(last["timestamp"])
                    if (datetime.datetime.now() - saved_time).days > 6:
                        since_id = None
                except (ValueError, TypeError):
                    since_id = None

            tweets = await client.search_recent_tweets(
                query=query,
                user_auth=twitter.use_key,
                since_id=since_id,
                max_results=max_results,
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
            if tweets.get("meta") and tweets.get("meta").get("newest_id"):
                last["since_id"] = tweets["meta"]["newest_id"]
                last["timestamp"] = datetime.datetime.now().isoformat()
                await self.skill_store.save_agent_skill_data(
                    context.agent_id, self.name, query, last
                )

            return tweets

        except Exception as e:
            logger.error(f"Error searching tweets: {str(e)}")
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
