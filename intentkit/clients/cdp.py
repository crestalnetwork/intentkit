import json
import logging
from typing import Dict, Optional

from cdp import EvmServerAccount
from coinbase_agentkit import (
    CdpEvmServerWalletProvider,
    CdpEvmServerWalletProviderConfig,
)

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData

_clients: Dict[str, "CdpClient"] = {}


class CdpClient:
    def __init__(self, agent_id: str, skill_store: SkillStoreABC) -> None:
        self._agent_id = agent_id
        self._skill_store = skill_store
        self._wallet_provider: Optional[CdpEvmServerWalletProvider] = None
        self._wallet_provider_config: Optional[CdpEvmServerWalletProviderConfig] = None

    async def get_wallet_provider(self) -> CdpEvmServerWalletProvider:
        if self._wallet_provider:
            return self._wallet_provider
        agent: Agent = await self._skill_store.get_agent_config(self._agent_id)
        agent_data: AgentData = await self._skill_store.get_agent_data(self._agent_id)
        network_id = agent.network_id or agent.cdp_network_id

        logger = logging.getLogger(__name__)

        # Get credentials from skill store system config
        api_key_id = self._skill_store.get_system_config("cdp_api_key_id")
        api_key_secret = self._skill_store.get_system_config("cdp_api_key_secret")
        wallet_secret = self._skill_store.get_system_config("cdp_wallet_secret")

        address = None

        # Attempt to override with any wallet-specific secret stored in wallet_data
        if agent_data.cdp_wallet_data:
            try:
                wallet_data = json.loads(agent_data.cdp_wallet_data)
                # Try to get address from the new format or fallback to old format
                if "default_address_id" in wallet_data:
                    address = wallet_data["default_address_id"]

                # Prefer wallet_secret stored alongside the wallet data if present
                if "wallet_secret" in wallet_data:
                    wallet_secret = wallet_data["wallet_secret"]
                elif "account_data" in wallet_data and wallet_data["account_data"]:
                    # Some versions may nest the secret inside account_data
                    wallet_secret = (
                        wallet_data["account_data"].get("wallet_secret")
                        or wallet_secret
                    )
            except json.JSONDecodeError:
                logger.warning(
                    "Invalid JSON in cdp_wallet_data for agent %s", self._agent_id
                )

        self._wallet_provider_config = CdpEvmServerWalletProviderConfig(
            api_key_id=api_key_id,
            api_key_secret=api_key_secret,
            network_id=network_id,
            address=address,
            wallet_secret=wallet_secret,
        )
        self._wallet_provider = CdpEvmServerWalletProvider(self._wallet_provider_config)
        return self._wallet_provider

    async def get_account(self) -> EvmServerAccount:
        """Get the account object from the wallet provider.

        Returns:
            EvmServerAccount: The account object that can be used for balance checks, transfers, etc.
        """
        wallet_provider = await self.get_wallet_provider()
        # Access the internal account object
        return wallet_provider._account

    async def get_provider_config(self) -> CdpEvmServerWalletProviderConfig:
        if not self._wallet_provider_config:
            await self.get_wallet_provider()
        return self._wallet_provider_config


async def get_cdp_client(agent_id: str, skill_store: SkillStoreABC) -> "CdpClient":
    if agent_id not in _clients:
        _clients[agent_id] = CdpClient(agent_id, skill_store)
    return _clients[agent_id]
