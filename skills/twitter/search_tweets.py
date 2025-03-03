import datetime
import logging
from typing import Type

from pydantic import BaseModel, Field

from .base import Tweet, TwitterBaseTool

logger = logging.getLogger(__name__)


class TwitterSearchTweetsInput(BaseModel):
    """Input for TwitterSearchTweets tool."""

    query: str = Field(description="The search query to find tweets")


class TwitterSearchTweetsOutput(BaseModel):
    """Output for TwitterSearchTweets tool."""

    tweets: list[Tweet]
    error: str | None = None


class TwitterSearchTweets(TwitterBaseTool):
    """Tool for searching recent tweets on Twitter.

    This tool uses the Twitter API v2 to search for recent tweets based on a query.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "twitter_search_tweets"
    description: str = "Search for recent tweets on Twitter using a query"
    args_schema: Type[BaseModel] = TwitterSearchTweetsInput

    async def _arun(
        self, query: str, max_results: int = 10, recent_only: bool = True
    ) -> TwitterSearchTweetsOutput:
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
        try:
            # Check rate limit only when not using OAuth
            if not self.twitter.use_key:
                is_rate_limited, error = await self.check_rate_limit(
                    max_requests=3, interval=60 * 24
                )
                if is_rate_limited:
                    return TwitterSearchTweetsOutput(
                        tweets=[], error=self._get_error_with_username(error)
                    )

            client = await self.twitter.get_client()
            if not client:
                return TwitterSearchTweetsOutput(
                    tweets=[],
                    error=self._get_error_with_username(
                        "Failed to get Twitter client. Please check your authentication."
                    ),
                )

            # Get since_id from store to avoid duplicate results
            last = await self.skill_store.get_agent_skill_data(
                self.agent_id, self.name, query
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
                user_auth=self.twitter.use_key,
                since_id=since_id,
                max_results=max_results,
                expansions=[
                    "referenced_tweets.id",
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
                    "description",
                    "public_metrics",
                    "location",
                    "connection_status",
                ],
                media_fields=["url"],
            )

            try:
                result = self.process_tweets_response(tweets)
            except Exception as e:
                logger.error(
                    self._get_error_with_username(
                        f"Error processing search results: {e}"
                    )
                )
                raise

            # Update the since_id in store for the next request
            if tweets.get("meta") and tweets.get("meta").get("newest_id"):
                last["since_id"] = tweets["meta"]["newest_id"]
                last["timestamp"] = datetime.datetime.now().isoformat()
                await self.skill_store.save_agent_skill_data(
                    self.agent_id, self.name, query, last
                )

            return TwitterSearchTweetsOutput(tweets=result)

        except Exception as e:
            logger.error(self._get_error_with_username(f"Error searching tweets: {e}"))
            return TwitterSearchTweetsOutput(
                tweets=[],
                error=self._get_error_with_username(f"Error searching tweets: {e}"),
            )

    def _run(self, query: str) -> TwitterSearchTweetsOutput:
        """Sync implementation of the tool.

        This method is deprecated since we now have native async implementation in _arun.
        """
        raise NotImplementedError(
            "Use _arun instead, which is the async implementation"
        )
