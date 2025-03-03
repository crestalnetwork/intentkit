import logging
from datetime import datetime, timedelta, timezone
from typing import Type

from pydantic import BaseModel

from .base import Tweet, TwitterBaseTool

logger = logging.getLogger(__name__)


class TwitterGetMentionsInput(BaseModel):
    """Input for TwitterGetMentions tool."""


class TwitterGetMentionsOutput(BaseModel):
    mentions: list[Tweet]
    error: str | None = None


class TwitterGetMentions(TwitterBaseTool):
    """Tool for getting mentions from Twitter.

    This tool uses the Twitter API v2 to retrieve mentions (tweets in which the authenticated
    user is mentioned) from Twitter.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "twitter_get_mentions"
    description: str = "Get tweets that mention the authenticated user"
    args_schema: Type[BaseModel] = TwitterGetMentionsInput

    def _run(self) -> TwitterGetMentionsOutput:
        """Run the get mentions tool.

        Returns:
            TwitterGetMentionsOutput: A structured output containing the mentions data.

        Raises:
            Exception: If there's an error accessing the Twitter API.
        """
        raise NotImplementedError("Use _arun instead")

    async def _arun(self) -> TwitterGetMentionsOutput:
        """Run the get mentions tool.

        Returns:
            TwitterGetMentionsOutput: A structured output containing the mentions data.

        Raises:
            Exception: If there's an error accessing the Twitter API.
        """
        is_rate_limited, error_msg = await self.check_rate_limit(1, 240)
        if is_rate_limited:
            return TwitterGetMentionsOutput(
                mentions=[],
                error=error_msg,
            )

        try:
            # get since id from store
            last = await self.skill_store.get_agent_skill_data(
                self.agent_id, self.name, "last"
            )
            last = last or {}
            max_results = 10
            since_id = last.get("since_id")
            if since_id:
                max_results = 30

            # Always get mentions for the last day
            start_time = datetime.now(tz=timezone.utc) - timedelta(days=1)

            client = await self.twitter.get_client()
            if not client:
                return TwitterGetMentionsOutput(
                    mentions=[],
                    error=self._get_error_with_username(
                        "Failed to get Twitter client. Please check your authentication."
                    ),
                )

            user_id = self.twitter.self_id
            if not user_id:
                return TwitterGetMentionsOutput(
                    mentions=[],
                    error=self._get_error_with_username(
                        "Failed to get Twitter user ID."
                    ),
                )

            mentions = await client.get_users_mentions(
                user_auth=self.twitter.use_key,
                id=user_id,
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

            try:
                result = self.process_tweets_response(mentions)
            except Exception as e:
                logger.error("Error processing mentions: %s", str(e))
                raise

            # Update since_id in store
            if mentions.get("meta") and mentions["meta"].get("newest_id"):
                last["since_id"] = mentions["meta"].get("newest_id")
                await self.skill_store.save_agent_skill_data(
                    self.agent_id, self.name, "last", last
                )

            return TwitterGetMentionsOutput(mentions=result)

        except Exception as e:
            logger.error("Error getting mentions: %s", str(e))
            return TwitterGetMentionsOutput(
                mentions=[], error=self._get_error_with_username(str(e))
            )
