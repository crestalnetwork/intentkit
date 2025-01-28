from typing import Type

from cdp import Wallet
from pydantic import BaseModel, Field

from abstracts.skill import IntentKitSkill, SkillStoreABC


class CdpBaseTool(IntentKitSkill):
    """Base class for CDP tools."""

    wallet: Wallet = Field(description="The wallet of the agent")
    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    agent_id: str = Field(description="The ID of the agent")
    store: SkillStoreABC = Field(description="The skill store for persisting data")
