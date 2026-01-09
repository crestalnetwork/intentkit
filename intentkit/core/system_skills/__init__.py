"""System skills for IntentKit agents.

These skills wrap core functionality and are available to all agents
without additional configuration.
"""

from intentkit.core.system_skills.call_agent import CallAgentSkill
from intentkit.core.system_skills.create_activity import CreateActivitySkill
from intentkit.core.system_skills.create_post import CreatePostSkill
from intentkit.core.system_skills.recent_activities import RecentActivitiesSkill

__all__ = [
    "CallAgentSkill",
    "CreateActivitySkill",
    "CreatePostSkill",
    "RecentActivitiesSkill",
]


def get_system_skills():
    """Get all system skills instances."""
    return [
        CallAgentSkill(),
        CreateActivitySkill(),
        CreatePostSkill(),
        RecentActivitiesSkill(),
    ]
