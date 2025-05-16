import logging
from datetime import datetime, timedelta, timezone

from epyxid import XID
from sqlalchemy import select

from app.core.engine import execute_agent
from app.core.skill import skill_store
from clients.twitter import get_twitter_client
from models.agent import Agent, AgentPluginData, AgentTable
from models.chat import AuthorType, ChatMessageAttachmentType, ChatMessageCreate
from models.db import get_session

logger = logging.getLogger(__name__)


async def run_twitter_agents():
    """Get all agents from the database which twitter is enabled,
    check their twitter config, get mentions, and process them."""
    async with get_session() as db:
        # Get all twitter-enabled agents
        agents = await db.scalars(
            select(AgentTable).where(
                AgentTable.twitter_entrypoint_enabled == True,  # noqa: E712
            )
        )

        for item in agents:
            agent = Agent.model_validate(item)
            try:
                try:
                    twitter = get_twitter_client(
                        agent.id, skill_store, agent.twitter_config
                    )
                    client = await twitter.get_client()
                except Exception as e:
                    logger.info(
                        f"Failed to initialize Twitter client for agent {agent.id}: {str(e)}"
                    )
                    continue

                # Get last mention id and processing time from plugin data
                plugin_data = await AgentPluginData.get(
                    agent.id, "twitter", "entrypoint"
                )
                since_id = None
                last_processed_time = None
                if plugin_data and plugin_data.data:
                    since_id = plugin_data.data.get("last_mention_id")
                    last_processed_time = plugin_data.data.get("last_processed_time")

                # Check if we should process tweets for this agent (at least 1 hour since last processing)
                current_time = datetime.now(tz=timezone.utc)
                should_process = True
                if not twitter.use_key and last_processed_time:
                    # Convert string timestamp back to datetime
                    last_time = datetime.fromisoformat(last_processed_time)
                    # Calculate time difference
                    time_diff = current_time - last_time
                    # Only process if more than 1 hour has passed
                    if time_diff < timedelta(hours=1):
                        logger.info(
                            f"Skipping agent {agent.id} - processed {time_diff.total_seconds() / 60:.1f} minutes ago"
                        )
                        should_process = False

                # Skip if we shouldn't process yet
                if not should_process:
                    continue
                # Always get mentions for the last day
                start_time = (
                    datetime.now(tz=timezone.utc) - timedelta(days=1)
                ).isoformat(timespec="milliseconds")
                # Get mentions
                mentions = await client.get_users_mentions(
                    user_auth=twitter.use_key,
                    id=twitter.self_id,
                    max_results=10,
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

                tweets = twitter.process_tweets_response(mentions)

                # Update last tweet id
                if mentions.get("meta") and mentions["meta"].get("newest_id"):
                    last_mention_id = mentions["meta"].get("newest_id")
                    current_time_str = current_time.isoformat()
                    plugin_data = AgentPluginData(
                        agent_id=agent.id,
                        plugin="twitter",
                        key="entrypoint",
                        data={
                            "last_mention_id": last_mention_id,
                            "last_processed_time": current_time_str,
                        },
                    )
                    await plugin_data.save()
                else:
                    raise Exception(
                        f"Failed to get last mention id for agent {agent.id}"
                    )

                # Process each mention
                for tweet in tweets:
                    logger.info(f"Processing mention for agent {agent.id}: {tweet}")
                    # skip self mentions
                    if str(tweet.author_id) == str(twitter.self_id):
                        continue
                    # because twitter react is all public, the memory shared by all public entrypoints
                    attachments = []
                    if tweet.attachments:
                        for attachment in tweet.attachments:
                            if attachment.type.startswith("image"):
                                attachments.append(
                                    {
                                        "type": ChatMessageAttachmentType.IMAGE,
                                        "url": attachment.url,
                                    }
                                )
                    message = ChatMessageCreate(
                        id=str(XID()),
                        agent_id=agent.id,
                        chat_id="public",
                        user_id=str(tweet.author_id),
                        author_id=str(tweet.author_id),
                        author_type=AuthorType.TWITTER,
                        thread_type=AuthorType.TWITTER,
                        message=tweet.text,
                        attachments=attachments,
                    )
                    response = await execute_agent(message)

                    # Reply to the tweet
                    await client.create_tweet(
                        text=response[-1].message,
                        user_auth=twitter.use_key,
                        in_reply_to_tweet_id=tweet.id,
                    )

            except Exception as e:
                logger.error(
                    f"Error processing twitter mentions for agent {agent.id}: {str(e)}"
                )
                continue
