from typing import Optional, Type

from cdp import EvmServerAccount
from coinbase_agentkit import CdpEvmServerWalletProvider
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
from intentkit.abstracts.skill import SkillStoreABC
from intentkit.clients import CdpClient, get_cdp_client
from intentkit.skills.base import IntentKitSkill
from intentkit.utils.chain import ChainProvider, NetworkId

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

    async def get_account(self, context: AgentContext) -> Optional[EvmServerAccount]:
        """Get the account object from the CDP client.

        Args:
            context: The skill context containing agent information.

        Returns:
            Optional[EvmServerAccount]: The account object if available.
        """
        client: CdpClient = await get_cdp_client(context.agent.id, self.skill_store)
        return await client.get_account()

    async def get_wallet_provider(
        self, context: AgentContext
    ) -> Optional[CdpEvmServerWalletProvider]:
        """Get the wallet provider from the CDP client.

        Args:
            context: The skill context containing agent information.

        Returns:
            Optional[CdpEvmServerWalletProvider]: The wallet provider if available.
        """
        client: CdpClient = await get_cdp_client(context.agent.id, self.skill_store)
        return await client.get_wallet_provider()

    def get_chain_provider(self, context: AgentContext) -> Optional[ChainProvider]:
        return self.skill_store.get_system_config("chain_provider")

    def get_main_tokens(self, context: AgentContext) -> list[str]:
        skill_config = context.agent.skill_config(self.category)
        if "main_tokens" in skill_config and skill_config["main_tokens"]:
            return skill_config["main_tokens"]
        return []

    def get_api_key(self) -> str:
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        api_key_provider = skill_config.get("api_key_provider")
        if api_key_provider == "platform":
            return self.skill_store.get_system_config("enso_api_token")
        # for backward compatibility, may only have api_token in skill_config
        elif skill_config.get("api_token"):
            return skill_config.get("api_token")
        else:
            raise ToolException(
                f"Invalid API key provider: {api_key_provider}, or no api_token in config"
            )

    @property
    def category(self) -> str:
        return "enso"
