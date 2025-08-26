import json
import logging
from typing import Dict, Optional

from bip32 import BIP32
from cdp import CdpClient as OriginCdpClient
from cdp import EvmServerAccount
from coinbase_agentkit import (
    CdpEvmServerWalletProvider,
    CdpEvmServerWalletProviderConfig,
)
from eth_keys.datatypes import PrivateKey
from eth_utils import to_checksum_address

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData

_clients: Dict[str, "CdpClient"] = {}
_origin_cdp_client: Optional[OriginCdpClient] = None

logger = logging.getLogger(__name__)


def bip39_seed_to_eth_keys(seed_hex: str) -> Dict[str, str]:
    """
    Converts a BIP39 seed to an Ethereum private key, public key, and address.

    Args:
        seed_hex: The BIP39 seed in hexadecimal format

    Returns:
        Dict containing private_key, public_key, and address
    """
    # Convert the hex seed to bytes
    seed_bytes = bytes.fromhex(seed_hex)

    # Derive the master key from the seed
    bip32 = BIP32.from_seed(seed_bytes)

    # Derive the Ethereum address using the standard derivation path
    private_key_bytes = bip32.get_privkey_from_path("m/44'/60'/0'/0/0")

    # Create a private key object
    private_key = PrivateKey(private_key_bytes)

    # Get the public key
    public_key = private_key.public_key

    # Get the Ethereum address
    address = public_key.to_address()

    return {
        "private_key": private_key.to_hex(),
        "public_key": public_key.to_hex(),
        "address": to_checksum_address(address),
    }


def get_origin_cdp_client(skill_store: SkillStoreABC) -> OriginCdpClient:
    global _origin_cdp_client
    if _origin_cdp_client:
        return _origin_cdp_client

    # Get credentials from skill store system config
    api_key_id = skill_store.get_system_config("cdp_api_key_id")
    api_key_secret = skill_store.get_system_config("cdp_api_key_secret")
    wallet_secret = skill_store.get_system_config("cdp_wallet_secret")

    _origin_cdp_client = OriginCdpClient(
        api_key_id=api_key_id,
        api_key_secret=api_key_secret,
        wallet_secret=wallet_secret,
    )
    return _origin_cdp_client


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

        # Get credentials from skill store system config
        api_key_id = self._skill_store.get_system_config("cdp_api_key_id")
        api_key_secret = self._skill_store.get_system_config("cdp_api_key_secret")
        wallet_secret = self._skill_store.get_system_config("cdp_wallet_secret")

        # already have address
        address = agent_data.evm_wallet_address

        # new agent or address not migrated yet
        if not address:
            # create cdp client for later use
            cdp_client = get_origin_cdp_client(self._skill_store)
            # try migrating from v1 cdp_wallet_data
            if agent_data.cdp_wallet_data:
                wallet_data = json.loads(agent_data.cdp_wallet_data)
                if not isinstance(wallet_data, dict):
                    raise ValueError("Invalid wallet data format")
                if wallet_data.get("default_address_id") and wallet_data.get("seed"):
                    # verify seed and convert to pk
                    keys = bip39_seed_to_eth_keys(wallet_data["seed"])
                    if keys["address"] != wallet_data["default_address_id"]:
                        raise ValueError(
                            "Bad wallet data, seed does not match default_address_id"
                        )
                    # try to import wallet to v2
                    logger.info("Migrating wallet data to v2...")
                    await cdp_client.evm.import_account(
                        name=agent.id,
                        private_key=keys["private_key"],
                    )
                    address = keys["address"]
                    logger.info("Migrated wallet data to v2 successfully: %s", address)
            # still not address
            if not address:
                logger.info("Creating new wallet...")
                new_account = await cdp_client.evm.create_account(
                    name=agent.id,
                )
                address = new_account.address
                logger.info("Created new wallet: %s", address)

            # do not close cached global client
            # now it should be created or migrated, store it
            agent_data.evm_wallet_address = address
            await agent_data.save()

        # it must have v2 account now, load agentkit wallet provider
        self._wallet_provider_config = CdpEvmServerWalletProviderConfig(
            api_key_id=api_key_id,
            api_key_secret=api_key_secret,
            network_id=network_id,
            address=address,
            wallet_secret=wallet_secret,
        )
        self._wallet_provider = CdpEvmServerWalletProvider(self._wallet_provider_config)
        # hack for cdp bug
        if network_id == "base-mainnet":
            self._wallet_provider._network.network_id = "base"
        elif network_id == "arbitrum-mainnet":
            self._wallet_provider._network.network_id = "arbitrum"
        elif network_id == "optimism-mainnet":
            self._wallet_provider._network.network_id = "optimism"
        elif network_id == "polygon-mainnet":
            self._wallet_provider._network.network_id = "polygon"
        elif network_id == "ethereum-mainnet":
            self._wallet_provider._network.network_id = "ethereum"
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
