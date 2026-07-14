"""Self Updater sub-agent definition."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from langchain_core.tools import BaseTool

from intentkit.core.lead.constants import compose_system_prompt
from intentkit.core.lead.tools.get_self_info import lead_get_self_info_tool
from intentkit.core.lead.tools.update_self import lead_update_self_tool
from intentkit.core.lead.tools.update_self_memory import lead_update_self_memory_tool
from intentkit.models.agent import Agent
from intentkit.models.llm_picker import pick_default_model


def get_self_updater_tools() -> Sequence[BaseTool]:
    """Return tools for the self-updater sub-agent."""
    return [
        lead_get_self_info_tool,
        lead_update_self_tool,
        lead_update_self_memory_tool,
    ]


def build_self_updater(team_id: str) -> Agent:
    """Build an in-memory Self Updater sub-agent."""
    now = datetime.now(timezone.utc)

    rules = (
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

    system_prompt = compose_system_prompt(
        purpose="Update the lead agent's own name, avatar, personality, and memory.",
        principles=(
            "1. Speak to users in their language.\n"
            "2. Always check current config before making changes.\n"
            "3. Confirm what will be changed before updating."
        ),
        rules=rules,
    )

    agent_data = {
        "id": f"team-{team_id}-self-updater",
        "owner": "system",
        "team_id": team_id,
        "name": "Self Updater",
        "model": pick_default_model(),
        "system_prompt": system_prompt,
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
