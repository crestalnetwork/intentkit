"""Slack skills."""

import logging
from typing import TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.slack.base import SlackBaseTool
from intentkit.skills.slack.get_channel import SlackGetChannel
from intentkit.skills.slack.get_message import SlackGetMessage
from intentkit.skills.slack.schedule_message import SlackScheduleMessage
from intentkit.skills.slack.send_message import SlackSendMessage

# we cache skills in system level, because they are stateless
_cache: dict[str, SlackBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    get_channel: SkillState
    get_message: SkillState
    schedule_message: SkillState
    send_message: SkillState


class Config(SkillConfig):
    """Configuration for Slack skills."""

    states: SkillStates
    slack_bot_token: str


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[SlackBaseTool]:
    """Get all Slack skills."""
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
        skill = get_slack_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_slack_skill(
    name: str,
    store: SkillStoreABC,
) -> SlackBaseTool:
    """Get a Slack skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested Slack skill
    """
    if name == "get_channel":
        if name not in _cache:
            _cache[name] = SlackGetChannel(
                skill_store=store,
            )
        return _cache[name]
    elif name == "get_message":
        if name not in _cache:
            _cache[name] = SlackGetMessage(
                skill_store=store,
            )
        return _cache[name]
    elif name == "schedule_message":
        if name not in _cache:
            _cache[name] = SlackScheduleMessage(
                skill_store=store,
            )
        return _cache[name]
    elif name == "send_message":
        if name not in _cache:
            _cache[name] = SlackSendMessage(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown Slack skill: {name}")
        return None
