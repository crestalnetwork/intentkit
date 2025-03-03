"""general skills."""

from abstracts.skill import SkillStoreABC
from app.core.system import SystemStore

from .base import GeneralBaseTool
from .timestamp import CurrentEpochTimestampTool, GetRelativeTimeParser


def get_general_skills(
    system_store: SystemStore,
    skill_store: SkillStoreABC,
    agent_store: SkillStoreABC,
    agent_id: str,
) -> list[GeneralBaseTool]:
    return [
        CurrentEpochTimestampTool(
            agent_id=agent_id,
            system_store=system_store,
            skill_store=skill_store,
            agent_store=agent_store,
        ),
        GetRelativeTimeParser(
            agent_id=agent_id,
            system_store=system_store,
            skill_store=skill_store,
            agent_store=agent_store,
        ),
    ]
