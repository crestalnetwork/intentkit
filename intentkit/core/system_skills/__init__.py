"""System skills for IntentKit agents.

These skills wrap core functionality and are available to all agents
without additional configuration.
"""

from intentkit.core.system_skills.base import SystemSkill
from intentkit.core.system_skills.call_agent import CallAgentSkill
from intentkit.core.system_skills.create_activity import CreateActivitySkill
from intentkit.core.system_skills.create_post import CreatePostSkill
from intentkit.core.system_skills.get_post import GetPostSkill
from intentkit.core.system_skills.recent_activities import RecentActivitiesSkill
from intentkit.core.system_skills.recent_posts import RecentPostsSkill

__all__ = [
    "SystemSkill",
    "CallAgentSkill",
    "CreateActivitySkill",
    "CreatePostSkill",
    "GetPostSkill",
    "RecentActivitiesSkill",
    "RecentPostsSkill",
]

# Cached singleton instances
_call_agent = CallAgentSkill()
_create_activity = CreateActivitySkill()
_recent_activities = RecentActivitiesSkill()
_create_post = CreatePostSkill()
_get_post = GetPostSkill()
_recent_posts = RecentPostsSkill()


def get_system_skills(
    enable_activity: bool = True,
    enable_post: bool = True,
) -> list[SystemSkill]:
    """Get system skills instances filtered by flags.

    Args:
        enable_activity: Whether to include activity skills. Defaults to True.
        enable_post: Whether to include post skills. Defaults to True.
    """
    skills: list[SystemSkill] = [_call_agent]
    if enable_activity:
        skills.append(_create_activity)
        skills.append(_recent_activities)
    if enable_post:
        skills.append(_create_post)
        skills.append(_get_post)
        skills.append(_recent_posts)
    return skills
