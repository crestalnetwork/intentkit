"""Self Updater sub-agent definition."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from langchain_core.tools import BaseTool

from intentkit.core.lead.skills.get_self_info import lead_get_self_info_skill
from intentkit.core.lead.skills.update_self import lead_update_self_skill
from intentkit.core.lead.skills.update_self_memory import lead_update_self_memory_skill
from intentkit.models.agent import Agent
from intentkit.models.llm_picker import pick_default_model


def get_self_updater_skills() -> Sequence[BaseTool]:
    """Return skills for the self-updater sub-agent."""
    return [
        lead_get_self_info_skill,
        lead_update_self_skill,
        lead_update_self_memory_skill,
    ]


def build_self_updater(team_id: str) -> Agent:
    """Build an in-memory Self Updater sub-agent."""
    now = datetime.now(timezone.utc)

    prompt = (
        "### Workflow\n\n"
        "1. Call `lead_get_self_info` first to see the current configuration.\n"
        "2. Use `lead_update_self` to change name, avatar, or personality.\n"
        "3. Use `lead_update_self_memory` to add or update memory.\n\n"
        "### Guidelines\n\n"
        "- Name: max 50 characters, should be professional and descriptive.\n"
        "- Avatar: must be a valid URL to an image.\n"
        "- Personality: a brief description of how the lead agent should behave.\n"
        "- Memory: information the lead agent should remember across conversations.\n"
    )

    agent_data = {
        "id": f"team-{team_id}-self-updater",
        "owner": "system",
        "team_id": team_id,
        "name": "Self Updater",
        "purpose": "Update the lead agent's own name, avatar, personality, and memory.",
        "principles": (
            "1. Speak to users in their language.\n"
            "2. Always check current config before making changes.\n"
            "3. Confirm what will be changed before updating."
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
