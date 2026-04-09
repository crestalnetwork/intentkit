"""Task Manager sub-agent definition."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from langchain_core.tools import BaseTool

from intentkit.core.lead.skills.add_autonomous_task import (
    lead_add_autonomous_task_skill,
)
from intentkit.core.lead.skills.delete_autonomous_task import (
    lead_delete_autonomous_task_skill,
)
from intentkit.core.lead.skills.edit_autonomous_task import (
    lead_edit_autonomous_task_skill,
)
from intentkit.core.lead.skills.list_autonomous_tasks import (
    lead_list_autonomous_tasks_skill,
)
from intentkit.core.lead.skills.list_team_agents import list_team_agents_skill
from intentkit.models.agent import Agent
from intentkit.models.llm_picker import pick_default_model


def get_task_manager_skills() -> Sequence[BaseTool]:
    """Return skills for the task manager sub-agent."""
    return [
        list_team_agents_skill,
        lead_list_autonomous_tasks_skill,
        lead_add_autonomous_task_skill,
        lead_edit_autonomous_task_skill,
        lead_delete_autonomous_task_skill,
    ]


def build_task_manager(team_id: str) -> Agent:
    """Build an in-memory Task Manager sub-agent."""
    now = datetime.now(timezone.utc)

    prompt = (
        "### Workflow\n\n"
        "1. If agent unspecified, call `lead_list_team_agents`.\n"
        "2. `lead_list_autonomous_tasks` to see existing tasks.\n"
        "3. Add, edit, or delete as needed.\n\n"
        "### Cron Expressions\n\n"
        "5 fields: min hour day month weekday\n"
        "- `*/5 * * * *` — every 5 min\n"
        "- `0 */2 * * *` — every 2 hours\n"
        "- `0 9 * * *` — daily 9:00 UTC\n"
        "- `0 9 * * 1-5` — weekdays 9:00 UTC\n\n"
        "### Conditional Tasks\n\n"
        "For condition-based tasks, create a polling task (e.g., every 5 min). "
        "Unless user says continuous, add self-deletion after success in the prompt.\n\n"
        "### Tips\n\n"
        "- `has_memory=True` only when needing context between runs\n"
        "- Disable (`enabled=False`) rather than delete for temporary pauses\n"
    )

    agent_data = {
        "id": f"team-{team_id}-task-manager",
        "owner": "system",
        "team_id": team_id,
        "name": "Task Manager",
        "purpose": "Manage autonomous scheduled tasks for team agents.",
        "principles": (
            "1. Speak to users in their language, but use English in task configuration.\n"
            "2. Use clear, descriptive task names."
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
