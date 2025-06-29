"""Twitter skills."""

import logging
from typing import TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.clients import TwitterClientConfig
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.twitter.base import TwitterBaseTool
from intentkit.skills.twitter.follow_user import TwitterFollowUser
from intentkit.skills.twitter.get_mentions import TwitterGetMentions
from intentkit.skills.twitter.get_timeline import TwitterGetTimeline
from intentkit.skills.twitter.get_user_by_username import TwitterGetUserByUsername
from intentkit.skills.twitter.get_user_tweets import TwitterGetUserTweets
from intentkit.skills.twitter.like_tweet import TwitterLikeTweet
from intentkit.skills.twitter.post_tweet import TwitterPostTweet
from intentkit.skills.twitter.reply_tweet import TwitterReplyTweet
from intentkit.skills.twitter.retweet import TwitterRetweet
from intentkit.skills.twitter.search_tweets import TwitterSearchTweets

# we cache skills in system level, because they are stateless
_cache: dict[str, TwitterBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    get_mentions: SkillState
    post_tweet: SkillState
    reply_tweet: SkillState
    get_timeline: SkillState
    get_user_by_username: SkillState
    get_user_tweets: SkillState
    follow_user: SkillState
    like_tweet: SkillState
    retweet: SkillState
    search_tweets: SkillState


class Config(SkillConfig, TwitterClientConfig):
    """Configuration for Twitter skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[TwitterBaseTool]:
    """Get all Twitter skills."""
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    result = []
    for name in available_skills:
        skill = get_twitter_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_twitter_skill(
    name: str,
    store: SkillStoreABC,
) -> TwitterBaseTool:
    """Get a Twitter skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested Twitter skill
    """
    if name == "get_mentions":
        if name not in _cache:
            _cache[name] = TwitterGetMentions(
                skill_store=store,
            )
        return _cache[name]
    elif name == "post_tweet":
        if name not in _cache:
            _cache[name] = TwitterPostTweet(
                skill_store=store,
            )
        return _cache[name]
    elif name == "reply_tweet":
        if name not in _cache:
            _cache[name] = TwitterReplyTweet(
                skill_store=store,
            )
        return _cache[name]
    elif name == "get_timeline":
        if name not in _cache:
            _cache[name] = TwitterGetTimeline(
                skill_store=store,
            )
        return _cache[name]
    elif name == "follow_user":
        if name not in _cache:
            _cache[name] = TwitterFollowUser(
                skill_store=store,
            )
        return _cache[name]
    elif name == "like_tweet":
        if name not in _cache:
            _cache[name] = TwitterLikeTweet(
                skill_store=store,
            )
        return _cache[name]
    elif name == "retweet":
        if name not in _cache:
            _cache[name] = TwitterRetweet(
                skill_store=store,
            )
        return _cache[name]
    elif name == "search_tweets":
        if name not in _cache:
            _cache[name] = TwitterSearchTweets(
                skill_store=store,
            )
        return _cache[name]
    elif name == "get_user_by_username":
        if name not in _cache:
            _cache[name] = TwitterGetUserByUsername(
                skill_store=store,
            )
        return _cache[name]
    elif name == "get_user_tweets":
        if name not in _cache:
            _cache[name] = TwitterGetUserTweets(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown Twitter skill: {name}")
        return None
