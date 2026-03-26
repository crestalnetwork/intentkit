import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel

from intentkit.clients.twitter import get_twitter_client

from .base import TwitterBaseTool

NAME = "twitter_get_mentions"
PROMPT = "Get tweets that mention you. If result_count is 0, don't retry."

logger = logging.getLogger(__name__)


class TwitterGetMentionsInput(BaseModel):
    """Input for TwitterGetMentions tool."""

    pass


class TwitterGetMentions(TwitterBaseTool):
    """Get tweets mentioning the authenticated user."""

    name: str = NAME
    description: str = PROMPT
    price: Decimal = Decimal("60")
    args_schema: ArgsSchema | None = TwitterGetMentionsInput

    async def _arun(self, **kwargs) -> dict[str, Any]:
        context = self.get_context()
        try:
            skill_config = context.agent.skill_config(self.category)
            twitter = get_twitter_client(
                agent_id=context.agent_id,
                config=skill_config,
            )
            client = await twitter.get_client()

            logger.debug("Use Key: %s", twitter.use_key)

            # Check rate limit only when not using OAuth
            if not twitter.use_key:
                await self.check_rate_limit(
                    max_requests=1,
                    interval=15,
                )

            # get since id from store
            last = await self.get_agent_skill_data("last")
            last = last or {}
            max_results = 10
            since_id = last.get("since_id")
            if since_id:
                max_results = 30

            # Always get mentions for the last day
            start_time = datetime.now(tz=UTC) - timedelta(days=1)

            user_id = twitter.self_id
            if not user_id:
                raise ToolException("Failed to get Twitter user ID.")

            mentions = cast(
                dict[str, Any],
                await client.get_users_mentions(
                    user_auth=twitter.use_key,
                    id=user_id,
                    max_results=max_results,
                    since_id=since_id,
                    start_time=start_time,
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
                ),
            )

            # Update since_id in store
            if mentions.get("meta") and mentions["meta"].get("newest_id"):
                last["since_id"] = mentions["meta"].get("newest_id")
                await self.save_agent_skill_data("last", last)

            return mentions

        except Exception as e:
            logger.error("[agent:%s]: %s", context.agent_id, e)
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
