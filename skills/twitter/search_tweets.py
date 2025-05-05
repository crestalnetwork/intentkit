import datetime
import logging
from typing import Type

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from clients.twitter import Tweet, get_twitter_client

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

    async def _arun(self, query: str, config: RunnableConfig, **kwargs) -> list[Tweet]:
        """Async implementation of the tool to search tweets.

        Args:
            query (str): The search query to use.
            max_results (int, optional): Maximum number of results to return. Defaults to 10.
            recent_only (bool, optional): Whether to only search recent tweets. Defaults to True.

        Returns:
            TwitterSearchTweetsOutput: A structured output containing the search results.

        Raises:
            Exception: If there's an error searching via the Twitter API.
        """
        max_results = 10
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
                    context.agent.id, max_requests=3, interval=60 * 24
                )

            # Get since_id from store to avoid duplicate results
            last = await self.skill_store.get_agent_skill_data(
                context.agent.id, self.name, query
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
                    context.agent.id, self.name, query, last
                )

            return tweets

        except Exception as e:
            logger.error(f"Error searching tweets: {str(e)}")
            raise type(e)(f"[agent:{context.agent.id}]: {e}") from e
