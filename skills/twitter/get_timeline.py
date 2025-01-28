import logging
from datetime import datetime, timedelta, timezone
from typing import Type

from pydantic import BaseModel

from .base import Tweet, TwitterBaseTool

logger = logging.getLogger(__name__)


class TwitterGetTimelineInput(BaseModel):
    """Input for TwitterGetTimeline tool."""


class TwitterGetTimelineOutput(BaseModel):
    tweets: list[Tweet]
    error: str | None = None


class TwitterGetTimeline(TwitterBaseTool):
    """Tool for getting the user's timeline from Twitter.

    This tool uses the Twitter API v2 to retrieve tweets from the authenticated user's
    timeline.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "twitter_get_timeline"
    description: str = "Get tweets from the authenticated user's timeline"
    args_schema: Type[BaseModel] = TwitterGetTimelineInput

    def _run(self, max_results: int = 10) -> TwitterGetTimelineOutput:
        """Run the tool to get the user's timeline.

        Args:
            max_results (int, optional): Maximum number of tweets to retrieve. Defaults to 10.

        Returns:
            TwitterGetTimelineOutput: A structured output containing the timeline data.

        Raises:
            Exception: If there's an error accessing the Twitter API.
        """
        try:
            # Ensure max_results is an integer
            max_results = int(max_results)

            # Check rate limit only when not using OAuth
            if not self.twitter.use_key:
                is_rate_limited, error = self.check_rate_limit(
                    max_requests=5, interval=15
                )
                if is_rate_limited:
                    return TwitterGetTimelineOutput(tweets=[], error=error)

            # get since id from store
            last = self.store.get_agent_skill_data(self.agent_id, self.name, "last")
            last = last or {}
            since_id = last.get("since_id")
            if since_id:
                max_results = 100

            # Always get timeline for the last day
            start_time = datetime.now(timezone.utc) - timedelta(days=1)

            client = self.twitter.get_client()
            if not client:
                return TwitterGetTimelineOutput(
                    tweets=[],
                    error=self._get_error_with_username(
                        "Failed to get Twitter client. Please check your authentication."
                    ),
                )

            timeline = client.get_home_timeline(
                user_auth=self.twitter.use_key,
                max_results=max_results,
                since_id=since_id,
                start_time=start_time,
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

            logger.debug(timeline)

            try:
                result = self.process_tweets_response(timeline)
            except Exception as e:
                logger.error("Error processing timeline: %s", str(e))
                raise

            # Update the since_id in store for the next request
            if timeline.get("meta") and timeline["meta"].get("newest_id"):
                last["since_id"] = timeline["meta"]["newest_id"]
                self.store.save_agent_skill_data(self.agent_id, self.name, "last", last)

            return TwitterGetTimelineOutput(tweets=result)

        except Exception as e:
            logger.error("Error getting timeline: %s", str(e))
            return TwitterGetTimelineOutput(
                tweets=[], error=self._get_error_with_username(str(e))
            )

    async def _arun(self) -> TwitterGetTimelineOutput:
        """Async implementation of the tool.

        This tool doesn't have a native async implementation, so we call the sync version.
        """
        return self._run()
