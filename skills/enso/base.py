from typing import Optional, Type

from cdp import Wallet
from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from clients.cdp import CdpClient, get_cdp_client
from skills.base import IntentKitSkill, SkillContext
from utils.chain import ChainProvider, NetworkId

base_url = "https://api.enso.finance"
default_chain_id = int(NetworkId.BaseMainnet)


class EnsoBaseTool(IntentKitSkill):
    """Base class for Enso tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    async def get_wallet(self, context: SkillContext) -> Optional[Wallet]:
        client: CdpClient = await get_cdp_client(context.agent.id, self.skill_store)
        return await client.get_wallet()

    def get_chain_provider(self, context: SkillContext) -> Optional[ChainProvider]:
        return self.skill_store.get_system_config("chain_provider")

    def get_main_tokens(self, context: SkillContext) -> list[str]:
        if "main_tokens" in context.config and context.config["main_tokens"]:
            return context.config["main_tokens"]
        return []

    def get_api_token(self, context: SkillContext) -> Optional[str]:
        if "api_token" in context.config and context.config["api_token"]:
            return context.config["api_token"]
        return self.skill_store.get_system_config("enso_api_token")

    @property
    def category(self) -> str:
        return "enso"
