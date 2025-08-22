import logging
from typing import Type

from pydantic import BaseModel

from intentkit.clients import get_twitter_client

from .base import TwitterBaseTool

logger = logging.getLogger(__name__)

NAME = "twitter_get_timeline"
PROMPT = (
    "Get tweets from your timeline, the result is a json object containing a list of tweets."
    'If the result is `{"meta": {"result_count": 0}}`, means no new tweets, don\'t retry this tool.'
)


class TwitterGetTimelineInput(BaseModel):
    """Input for TwitterGetTimeline tool."""


class TwitterGetTimeline(TwitterBaseTool):
    """Tool for getting the user's timeline from Twitter.

    This tool uses the Twitter API v2 to retrieve tweets from the authenticated user's
    timeline.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = TwitterGetTimelineInput

    async def _arun(self, **kwargs):
        context = self.get_context()
        try:
            # Ensure max_results is an integer
            max_results = 10

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

            # get since id from store
            last = await self.skill_store.get_agent_skill_data(
                context.agent_id, self.name, "last"
            )
            last = last or {}
            since_id = last.get("since_id")

            user_id = twitter.self_id
            if not user_id:
                raise ValueError("Failed to get Twitter user ID.")

            timeline = await client.get_home_timeline(
                user_auth=twitter.use_key,
                max_results=max_results,
                since_id=since_id,
                exclude=["replies"],
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
            if timeline.get("meta") and timeline["meta"].get("newest_id"):
                last["since_id"] = timeline["meta"]["newest_id"]
                await self.skill_store.save_agent_skill_data(
                    context.agent_id, self.name, "last", last
                )

            return timeline

        except Exception as e:
            logger.error("Error getting timeline: %s", str(e))
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
