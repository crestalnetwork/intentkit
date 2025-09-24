from decimal import Decimal
from typing import Optional, Type

from coinbase_agentkit import CdpEvmWalletProvider
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
from intentkit.abstracts.skill import SkillStoreABC
from intentkit.clients import CdpClient, get_cdp_client
from intentkit.skills.base import IntentKitSkill
from intentkit.utils.chain import ChainProvider, Network, network_to_id

base_url = "https://api.enso.finance"


class EnsoBaseTool(IntentKitSkill):
    """Base class for Enso tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    async def get_wallet_provider(
        self, context: AgentContext
    ) -> Optional[CdpEvmWalletProvider]:
        """Get the wallet provider from the CDP client.

        Args:
            context: The skill context containing agent information.

        Returns:
            Optional[CdpEvmWalletProvider]: The wallet provider if available.
        """
        client: CdpClient = await get_cdp_client(context.agent.id, self.skill_store)
        return await client.get_wallet_provider()

    async def get_wallet_address(self, context: AgentContext) -> str:
        client: CdpClient = await get_cdp_client(context.agent.id, self.skill_store)
        provider_config = await client.get_provider_config()
        if not provider_config.address:
            raise ToolException("wallet address not found for agent")
        return provider_config.address

    def get_chain_provider(self, context: AgentContext) -> Optional[ChainProvider]:
        return self.skill_store.get_system_config("chain_provider")

    def get_main_tokens(self, context: AgentContext) -> list[str]:
        skill_config = context.agent.skill_config(self.category)
        if "main_tokens" in skill_config and skill_config["main_tokens"]:
            return skill_config["main_tokens"]
        return []

    def get_api_token(self, context: AgentContext) -> str:
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

    def resolve_chain_id(
        self, context: AgentContext, chain_id: Optional[int] = None
    ) -> int:
        if chain_id:
            return chain_id

        agent = context.agent
        try:
            network = Network(agent.network_id)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ToolException(
                f"Unsupported network configured for agent: {agent.network_id}"
            ) from exc

        network_id = network_to_id.get(network)
        if network_id is None:
            raise ToolException(
                f"Unable to determine chain id for network: {agent.network_id}"
            )
        return int(network_id)

    @property
    def category(self) -> str:
        return "enso"


def format_amount_with_decimals(
    amount: object, decimals: Optional[int]
) -> Optional[str]:
    if amount is None or decimals is None:
        return None

    try:
        value = Decimal(str(amount)) / (Decimal(10) ** decimals)
        return format(value, "f")
    except Exception:  # pragma: no cover - defensive
        return None
