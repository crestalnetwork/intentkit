from typing import Type

from pydantic import BaseModel, Field

from abstracts.agent import AgentStoreABC
from abstracts.skill import IntentKitSkill, SkillStoreABC

base_url = "https://staging.crossmint.com"


class GoatBaseTool(IntentKitSkill):
    """Base class for Goat tools."""

    private_key: str = Field(description="Wallet Private Key")
    rpc_node: str | None = Field(None, description="RPC nodes for different networks")
    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    agent_id: str = Field(description="The ID of the agent")
    agent_store: AgentStoreABC = Field(
        description="The agent store for persisting data"
    )
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )
