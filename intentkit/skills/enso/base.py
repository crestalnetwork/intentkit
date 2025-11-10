from decimal import Decimal

from coinbase_agentkit import CdpEvmWalletProvider
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
from intentkit.clients import get_wallet_provider as get_agent_wallet_provider
from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill
from intentkit.utils.chain import (
    ChainProvider,
    network_to_id,
    resolve_quicknode_network,
)

base_url = "https://api.enso.finance"


class EnsoBaseTool(IntentKitSkill):
    """Base class for Enso tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: type[BaseModel]

    async def get_wallet_provider(self, context: AgentContext) -> CdpEvmWalletProvider:
        """Get the wallet provider from the CDP client.

        Args:
            context: The skill context containing agent information.

        Returns:
            CdpEvmWalletProvider | None: The wallet provider if available.
        """
        return await get_agent_wallet_provider(context.agent)

    async def get_wallet_address(self, context: AgentContext) -> str:
        provider: CdpEvmWalletProvider = await self.get_wallet_provider(context)
        return provider.get_address()

    def get_chain_provider(self, context: AgentContext) -> ChainProvider | None:
        return config.chain_provider

    def get_main_tokens(self, context: AgentContext) -> list[str]:
        skill_config = context.agent.skill_config(self.category)
        if "main_tokens" in skill_config and skill_config["main_tokens"]:
            return skill_config["main_tokens"]
        return []

    def get_api_token(self, context: AgentContext) -> str:
        skill_config = context.agent.skill_config(self.category)
        api_key_provider = skill_config.get("api_key_provider")
        if api_key_provider == "platform":
            return config.enso_api_token
        # for backward compatibility, may only have api_token in skill_config
        elif skill_config.get("api_token"):
            return skill_config.get("api_token")
        else:
            raise ToolException(
                f"Invalid API key provider: {api_key_provider}, or no api_token in config"
            )

    def resolve_chain_id(
        self, context: AgentContext, chain_id: int | None = None
    ) -> int:
        if chain_id:
            return chain_id

        agent = context.agent
        try:
            network = resolve_quicknode_network(agent.network_id)
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


def format_amount_with_decimals(amount: object, decimals: int | None) -> str | None:
    if amount is None or decimals is None:
        return None

    try:
        value = Decimal(str(amount)) / (Decimal(10) ** decimals)
        return format(value, "f")
    except Exception:  # pragma: no cover - defensive
        return None
