from typing import Dict, Optional

from cdp import Wallet
from coinbase_agentkit import (
    CdpWalletProvider,
    CdpWalletProviderConfig,
)

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData

_clients: Dict[str, "CdpClient"] = {}


class CdpClient:
    def __init__(self, agent_id: str, skill_store: SkillStoreABC) -> None:
        self._agent_id = agent_id
        self._skill_store = skill_store
        self._wallet_provider: Optional[CdpWalletProvider] = None
        self._wallet_provider_config: Optional[CdpWalletProviderConfig] = None

    async def get_wallet_provider(self) -> CdpWalletProvider:
        if self._wallet_provider:
            return self._wallet_provider
        agent: Agent = await self._skill_store.get_agent_config(self._agent_id)
        agent_data: AgentData = await self._skill_store.get_agent_data(self._agent_id)
        network_id = agent.network_id or agent.cdp_network_id
        self._wallet_provider_config = CdpWalletProviderConfig(
            api_key_name=self._skill_store.get_system_config("cdp_api_key_name"),
            api_key_private_key=self._skill_store.get_system_config(
                "cdp_api_key_private_key"
            ),
            network_id=network_id,
            wallet_data=agent_data.cdp_wallet_data,
        )
        self._wallet_provider = CdpWalletProvider(self._wallet_provider_config)
        return self._wallet_provider

    async def get_wallet(self) -> Wallet:
        wallet_provider = await self.get_wallet_provider()
        return wallet_provider._wallet

    async def get_provider_config(self) -> CdpWalletProviderConfig:
        if not self._wallet_provider_config:
            await self.get_wallet_provider()
        return self._wallet_provider_config


async def get_cdp_client(agent_id: str, skill_store: SkillStoreABC) -> "CdpClient":
    if agent_id not in _clients:
        _clients[agent_id] = CdpClient(agent_id, skill_store)
    return _clients[agent_id]
