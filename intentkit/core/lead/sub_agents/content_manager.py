"""Content Manager sub-agent definition."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from langchain_core.tools import BaseTool

from intentkit.core.lead.skills.get_post import lead_get_post_skill
from intentkit.core.lead.skills.recent_team_activities import (
    lead_recent_team_activities_skill,
)
from intentkit.core.lead.skills.recent_team_posts import lead_recent_team_posts_skill
from intentkit.models.agent import Agent
from intentkit.models.llm_picker import pick_default_model


def get_content_manager_skills() -> Sequence[BaseTool]:
    """Return skills for the content manager sub-agent."""
    return [
        lead_recent_team_activities_skill,
        lead_recent_team_posts_skill,
        lead_get_post_skill,
    ]


def build_content_manager(team_id: str) -> Agent:
    """Build an in-memory Content Manager sub-agent."""
    now = datetime.now(timezone.utc)

    prompt = (
        "### Workflow\n\n"
        "1. Use `lead_recent_team_activities` to see recent team activities.\n"
        "2. Use `lead_recent_team_posts` to browse recent team posts.\n"
        "3. Use `lead_get_post` with a post ID to read full post content.\n\n"
        "### Guidelines\n\n"
        "- When summarizing activities, highlight key actions and trends.\n"
        "- When reviewing posts, provide concise summaries.\n"
        "- Use post IDs from the list to fetch full content when needed.\n"
    )

    agent_data = {
        "id": f"team-{team_id}-content-manager",
        "owner": "system",
        "team_id": team_id,
        "name": "Content Manager",
        "purpose": "Read and review team activities and posts.",
        "principles": (
            "1. Speak to users in their language.\n"
            "2. Provide clear, concise summaries.\n"
            "3. Reference specific post IDs when discussing content."
        ),
        "model": pick_default_model(),
        "prompt": prompt,
        "temperature": 0.2,
        "search_internet": False,
        "super_mode": False,
        "enable_todo": False,
        "enable_activity": False,
        "enable_post": False,
        "enable_long_term_memory": False,
        "sub_agents": None,
        "skills": {
            "ui": {
                "enabled": True,
                "states": {
                    "ui_show_card": "private",
                    "ui_ask_user": "private",
                },
            },
        },
        "created_at": now,
        "updated_at": now,
    }

    return Agent.model_validate(agent_data)
