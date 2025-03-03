from typing import Type

from pydantic import BaseModel, Field

from abstracts.agent import AgentStoreABC
from abstracts.skill import IntentKitSkill, SkillStoreABC
from app.core.system import SystemStore


class GeneralBaseTool(IntentKitSkill):
    """Base class for General tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    agent_id: str = Field(description="The ID of the agent")
    system_store: SystemStore = Field(
        description="The global store for persisted data retrieval"
    )
    agent_store: AgentStoreABC = Field(
        description="The agent store for persisting data"
    )
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )
