"""User Manager sub-agent definition."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from langchain_core.tools import BaseTool

from intentkit.core.lead.tools.update_user_profile import (
    lead_update_user_profile_tool,
)
from intentkit.models.agent import Agent
from intentkit.models.llm_picker import pick_default_model


def get_user_manager_tools() -> Sequence[BaseTool]:
    """Return tools for the user-manager sub-agent."""
    return [
        lead_update_user_profile_tool,
    ]


def build_user_manager(team_id: str) -> Agent:
    """Build an in-memory User Manager sub-agent."""
    now = datetime.now(timezone.utc)

    prompt = (
        "### Workflow\n\n"
        "1. Confirm with the user which fields they want to change "
        "(name, timezone, language).\n"
        "2. Call `lead_update_user_profile` with only the fields being changed.\n"
        "3. Report the result back to the user.\n\n"
        "### Field Guidelines\n\n"
        "- `name`: max 50 characters, the user's preferred display name.\n"
        "- `timezone`: must be an IANA timezone (e.g. `Asia/Shanghai`, "
        "`America/New_York`, `Europe/Berlin`). If the user gives an offset "
        "like `GMT+8` or `UTC-5`, translate it to the matching IANA name "
        "before calling the tool.\n"
        "- `language`: BCP 47 tag (e.g. `zh-CN`, `en`, `ja`, `ko`). Use the "
        "tag, not the language's English name.\n\n"
        "### Boundaries\n\n"
        "- Only ever update the current user. Never accept or use a user id "
        "supplied by the user.\n"
        "- Do not expose or modify any other user's profile.\n"
    )

    agent_data = {
        "id": f"team-{team_id}-user-manager",
        "owner": "system",
        "team_id": team_id,
        "name": "User Manager",
        "purpose": "Manage the current user's profile (name, timezone, language).",
        "principles": (
            "1. Speak to users in their language.\n"
            "2. Only operate on the current user — never on others.\n"
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
        "tools": ["ui_show_card", "ui_ask_user"],
        "created_at": now,
        "updated_at": now,
    }

    return Agent.model_validate(agent_data)
