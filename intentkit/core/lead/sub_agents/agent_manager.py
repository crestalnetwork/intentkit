"""Agent Manager sub-agent definition."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from langchain_core.tools import BaseTool

from intentkit.core.lead.skills.create_team_agent import create_team_agent_skill
from intentkit.core.lead.skills.get_team_agent import get_team_agent_skill
from intentkit.core.lead.skills.get_team_info import get_team_info_skill
from intentkit.core.lead.skills.list_skills import lead_list_available_skills_skill
from intentkit.core.lead.skills.list_team_agents import list_team_agents_skill
from intentkit.core.lead.skills.llm import lead_get_available_llms_skill
from intentkit.core.lead.skills.update_team_agent import update_team_agent_skill
from intentkit.models.agent import Agent
from intentkit.models.llm_picker import pick_default_model


def get_agent_manager_skills() -> Sequence[BaseTool]:
    """Return skills for the agent manager sub-agent."""
    return [
        get_team_info_skill,
        list_team_agents_skill,
        create_team_agent_skill,
        get_team_agent_skill,
        update_team_agent_skill,
        lead_get_available_llms_skill,
        lead_list_available_skills_skill,
    ]


def build_agent_manager(team_id: str) -> Agent:
    """Build an in-memory Agent Manager sub-agent."""
    now = datetime.now(timezone.utc)

    prompt = (
        "### Workflow\n\n"
        "- Call `lead_list_team_agents` first when asked about existing agents.\n"
        "- Call `lead_get_team_agent` before updating to see current config.\n\n"
        "### Agent Creation\n\n"
        "Guide user through:\n"
        "1. Name, slug, and purpose\n"
        "2. Model — `lead_get_available_llms` for options. "
        "High intelligence for complex reasoning, high speed for simple tasks.\n"
        "3. Skills — `lead_list_available_skills` for options. Keep under 20.\n"
        "4. Additional settings as needed\n\n"
        "### Skill Configuration\n\n"
        '```\n"skills": {"category": {"states": {"skill1": "public"}, "enabled": true}}\n```\n'
        "`enabled` is category-level. `states` controls individual skills. "
        "Use `private` for sensitive content, `public` for all users.\n\n"
        "### Agent Fields Reference\n\n"
        "- `name`: Display name (max 50 chars)\n"
        "- `purpose`, `personality`, `principles`: Agent character\n"
        "- `model`: LLM model ID\n"
        "- `prompt`: Base system prompt\n"
        "- `prompt_append`: Additional system prompt (higher priority)\n"
        "- `temperature`: Randomness (0.0~2.0, lower for rigorous tasks)\n"
        "- `skills`: Skill configurations dict\n"
        "- `slug`: URL-friendly slug (immutable once set)\n"
        "- `sub_agents`: List of sub-agent IDs or slugs\n"
        "- `sub_agent_prompt`: Instructions for how to use sub-agents\n"
        "- `enable_todo`, `enable_activity`, `enable_post`: Feature toggles\n"
        "- `enable_long_term_memory`: Enable long-term memory\n"
        "- `super_mode`: Higher recursion limit\n"
        "- `search_internet`: LLM native internet search\n"
        "- `visibility`: PRIVATE(0), TEAM(10), PUBLIC(20)\n"
    )

    agent_data = {
        "id": f"team-{team_id}-agent-manager",
        "owner": "system",
        "team_id": team_id,
        "name": "Agent Manager",
        "purpose": "Create, configure, and update team agents.",
        "principles": (
            "1. Speak to users in their language, but use English in agent configuration.\n"
            "2. All changes are directly deployed (no draft flow).\n"
            "3. Update is override — provide complete field values, not just changes."
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
