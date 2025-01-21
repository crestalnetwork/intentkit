from typing import Type

from pydantic import BaseModel, Field

from abstracts.skill import IntentKitSkill, SkillStoreABC

base_url = "https://api.enso.finance"
default_chain_id = 8453
default_protocol_slug = "aave-v3"


class EnsoBaseTool(IntentKitSkill):
    """Base class for Twitter tools."""

    api_token: str = Field(description="API token")
    main_tokens: list[str] = Field(description="Main supported tokens")
    from_address: str = Field(description="The address of the agent's wallet")
    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    agent_id: str = Field(description="The ID of the agent")
    store: SkillStoreABC = Field(description="The skill store for persisting data")
