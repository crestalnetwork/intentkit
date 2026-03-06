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


def get_system_skills():
    """Get all system skills instances."""
    return [
        CallAgentSkill(),
        CreateActivitySkill(),
        CreatePostSkill(),
        GetPostSkill(),
        RecentActivitiesSkill(),
        RecentPostsSkill(),
    ]
