"""System skills for IntentKit agents.

These skills wrap core functionality and are available to all agents
without additional configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from intentkit.core.system_skills.base import SystemSkill
from intentkit.core.system_skills.call_agent import CallAgentSkill
from intentkit.core.system_skills.create_activity import CreateActivitySkill
from intentkit.core.system_skills.create_post import CreatePostSkill
from intentkit.core.system_skills.current_time import CurrentTimeSkill
from intentkit.core.system_skills.get_post import GetPostSkill
from intentkit.core.system_skills.read_webpage import (
    ReadWebpageCloudflareSkill,
    ReadWebpageZaiSkill,
)
from intentkit.core.system_skills.recent_activities import RecentActivitiesSkill
from intentkit.core.system_skills.recent_posts import RecentPostsSkill
from intentkit.core.system_skills.search_web import SearchWebZaiSkill
from intentkit.core.system_skills.update_memory import UpdateMemorySkill

if TYPE_CHECKING:
    from intentkit.models.agent import Agent

__all__ = [
    "SystemSkill",
    "CallAgentSkill",
    "CreateActivitySkill",
    "CreatePostSkill",
    "CurrentTimeSkill",
    "GetPostSkill",
    "ReadWebpageCloudflareSkill",
    "ReadWebpageZaiSkill",
    "SearchWebZaiSkill",
    "RecentActivitiesSkill",
    "RecentPostsSkill",
    "UpdateMemorySkill",
    "read_webpage_cloudflare",
    "read_webpage_zai",
    "search_web_zai",
]

# Cached singleton instances
_call_agent = CallAgentSkill()
_create_activity = CreateActivitySkill()
_current_time = CurrentTimeSkill()
_recent_activities = RecentActivitiesSkill()
_create_post = CreatePostSkill()
_get_post = GetPostSkill()
_recent_posts = RecentPostsSkill()
_update_memory = UpdateMemorySkill()
read_webpage_cloudflare = ReadWebpageCloudflareSkill()
read_webpage_zai = ReadWebpageZaiSkill()
search_web_zai = SearchWebZaiSkill()


def get_system_skills(agent: Agent) -> list[SystemSkill]:
    """Get system skills instances based on agent configuration.

    Args:
        agent: Agent configuration object. The following fields are used:
            - enable_activity: Whether to include activity skills (default True).
            - enable_post: Whether to include post skills (default True).
            - enable_long_term_memory: Whether to include memory skill.
            - sub_agents: Whether to include call_agent skill.
            - search_internet: Whether to include read_webpage skill.
    """
    skills: list[SystemSkill] = [_current_time]
    if agent.sub_agents:
        skills.append(_call_agent)

    enable_activity = (
        agent.enable_activity if agent.enable_activity is not None else True
    )
    if enable_activity:
        skills.append(_create_activity)
        skills.append(_recent_activities)

    enable_post = agent.enable_post if agent.enable_post is not None else True
    if enable_post:
        skills.append(_create_post)
        skills.append(_get_post)
        skills.append(_recent_posts)

    if agent.enable_long_term_memory:
        skills.append(_update_memory)
    return skills
