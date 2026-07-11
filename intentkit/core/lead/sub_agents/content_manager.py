"""Content Manager sub-agent definition."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from langchain_core.tools import BaseTool

from intentkit.core.lead.constants import compose_system_prompt
from intentkit.core.lead.tools.get_post import lead_get_post_tool
from intentkit.core.lead.tools.recent_team_activities import (
    lead_recent_team_activities_tool,
)
from intentkit.core.lead.tools.recent_team_posts import lead_recent_team_posts_tool
from intentkit.models.agent import Agent
from intentkit.models.llm_picker import pick_default_model


def get_content_manager_tools() -> Sequence[BaseTool]:
    """Return tools for the content manager sub-agent."""
    return [
        lead_recent_team_activities_tool,
        lead_recent_team_posts_tool,
        lead_get_post_tool,
    ]


def build_content_manager(team_id: str) -> Agent:
    """Build an in-memory Content Manager sub-agent."""
    now = datetime.now(timezone.utc)

    system_prompt = compose_system_prompt(
        purpose="Read and review team activities and posts.",
        principles=(
            "1. Speak to users in their language.\n"
            "2. Provide clear, concise summaries.\n"
            "3. Reference specific post IDs when discussing content."
        ),
        rules=(
            "### Workflow\n\n"
            "1. Use `lead_recent_team_activities` to see recent team activities.\n"
            "2. Use `lead_recent_team_posts` to browse recent team posts.\n"
            "3. Use `lead_get_post` with a post ID to read full post content.\n\n"
            "### Guidelines\n\n"
            "- When summarizing activities, highlight key actions and trends.\n"
            "- When reviewing posts, provide concise summaries.\n"
            "- Use post IDs from the list to fetch full content when needed.\n"
        ),
    )

    agent_data = {
        "id": f"team-{team_id}-content-manager",
        "owner": "system",
        "team_id": team_id,
        "name": "Content Manager",
        "model": pick_default_model(),
        "system_prompt": system_prompt,
        "temperature": 0.2,
        "search_internet": False,
        "enable_todo": False,
        "enable_activity": False,
        "enable_post": False,
        "sub_agents": None,
        # ui_show_card / ui_ask_user are interactive_only system tools now;
        # ToolBindingMiddleware drops them per request for sub-agent runs
        "tools": None,
        "created_at": now,
        "updated_at": now,
    }

    return Agent.model_validate(agent_data)
