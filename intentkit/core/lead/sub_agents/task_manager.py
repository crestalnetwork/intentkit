"""Task Manager sub-agent: team-level autonomous (cron) task scheduling."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from langchain_core.tools import BaseTool

from intentkit.core.lead.constants import compose_system_prompt
from intentkit.core.lead.tools.add_autonomous_task import (
    lead_add_autonomous_task_tool,
)
from intentkit.core.lead.tools.delete_autonomous_task import (
    lead_delete_autonomous_task_tool,
)
from intentkit.core.lead.tools.edit_autonomous_task import (
    lead_edit_autonomous_task_tool,
)
from intentkit.core.lead.tools.list_autonomous_tasks import (
    lead_list_autonomous_tasks_tool,
)
from intentkit.core.lead.tools.list_team_agents import list_team_agents_tool
from intentkit.models.agent import Agent
from intentkit.models.llm_picker import pick_default_model


def get_task_manager_tools() -> Sequence[BaseTool]:
    """Return tools for the task manager sub-agent."""
    return [
        list_team_agents_tool,
        lead_list_autonomous_tasks_tool,
        lead_add_autonomous_task_tool,
        lead_edit_autonomous_task_tool,
        lead_delete_autonomous_task_tool,
    ]


def build_task_manager(team_id: str) -> Agent:
    """Build an in-memory Task Manager sub-agent."""
    now = datetime.now(UTC)

    rules = (
        "### Autonomous Tasks\n\n"
        "Tasks belong to the team and run on a cron schedule. Each run executes "
        "either directly on a pinned agent or through the team lead.\n\n"
        "Tools:\n"
        "- `lead_list_autonomous_tasks` — list the team's tasks (call before "
        "edit/delete to discover task IDs).\n"
        "- `lead_add_autonomous_task` — schedule a new task.\n"
        "- `lead_edit_autonomous_task` — update fields on an existing task.\n"
        "- `lead_delete_autonomous_task` — remove a task.\n"
        "- `lead_list_team_agents` — list team agents (to pick a target agent or "
        "to write a delegation prompt).\n\n"
        "### Targeting\n\n"
        "- Set `target_agent_id` to run the task directly on a specific agent "
        "(cheaper, deterministic). Use `lead_list_team_agents` to get valid IDs.\n"
        "- Leave `target_agent_id` empty to let the team lead read the prompt and "
        "decide which agent to delegate to at run time. In that case, write the "
        "prompt so the lead knows what to do (e.g. name the agent to use).\n\n"
        "### Workflow\n\n"
        "1. If the user did not specify a target agent and one is needed, call "
        "`lead_list_team_agents`.\n"
        "2. Call `lead_list_autonomous_tasks` before editing or deleting.\n"
        "3. Apply the change.\n\n"
        "Cron expressions (5 fields: min hour day month weekday):\n"
        "- `*/5 * * * *` — every 5 min (shortest allowed)\n"
        "- `0 */2 * * *` — every 2 hours\n"
        "- `0 9 * * *` — daily 9:00 UTC\n"
        "- `0 9 * * 1-5` — weekdays 9:00 UTC\n\n"
        "Conditional tasks: for condition-based work, schedule a polling task "
        "(e.g. every 5 min). Unless the user wants it to run forever, tell the "
        "task to delete itself once the condition is met.\n\n"
        "Tips:\n"
        "- Runs never retain conversation history; if a task must carry "
        "facts between runs, tell it (in its prompt) to record them with "
        "update_memory — each task has its own cron-scoped memory.\n"
        "- Prefer disabling (`enabled=False`) over deleting for temporary pauses.\n"
    )

    system_prompt = compose_system_prompt(
        purpose=(
            "Schedule and manage the team's autonomous (cron) tasks, including "
            "which agent each task targets."
        ),
        principles=(
            "1. Speak to users in their language, but use English in task configuration.\n"
            "2. All changes are applied immediately.\n"
            "3. Update is override — provide complete field values, not just changes."
        ),
        rules=rules,
    )

    agent_data = {
        "id": f"team-{team_id}-task-manager",
        "owner": "system",
        "team_id": team_id,
        "name": "Task Manager",
        "model": pick_default_model(),
        "system_prompt": system_prompt,
        "search_internet": False,
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
