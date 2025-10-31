import asyncio
import json
import logging
from typing import Dict, Tuple

from bip32 import BIP32
from cdp import CdpClient, EvmServerAccount  # noqa: E402
from coinbase_agentkit import (  # noqa: E402
    CdpEvmWalletProvider,
    CdpEvmWalletProviderConfig,
)
from eth_keys.datatypes import PrivateKey
from eth_utils import to_checksum_address

from intentkit.config.config import config
from intentkit.models.agent import Agent, AgentTable  # noqa: E402
from intentkit.models.agent_data import AgentData
from intentkit.models.db import get_session
from intentkit.utils.error import IntentKitAPIError  # noqa: E402

_wallet_providers: Dict[str, Tuple[str, str, CdpEvmWalletProvider]] = {}
_cdp_client: CdpClient | None = None

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


def get_cdp_client() -> CdpClient:
    global _cdp_client
    if _cdp_client:
        return _cdp_client

    # Get credentials from global configuration
    api_key_id = config.cdp_api_key_id
    api_key_secret = config.cdp_api_key_secret
    wallet_secret = config.cdp_wallet_secret

    _cdp_client = CdpClient(
        api_key_id=api_key_id,
        api_key_secret=api_key_secret,
        wallet_secret=wallet_secret,
    )
    return _cdp_client


def _assert_cdp_wallet_provider(agent: Agent) -> None:
    if agent.wallet_provider != "cdp":
        raise IntentKitAPIError(
            400,
            "BadWalletProvider",
            "Your agent wallet provider is not cdp but you selected a skill that requires a cdp wallet.",
        )


async def _ensure_evm_account(
    agent: Agent, agent_data: AgentData | None = None
) -> Tuple[EvmServerAccount, AgentData]:
    cdp_client = get_cdp_client()
    agent_data = agent_data or await AgentData.get(agent.id)
    address = agent_data.evm_wallet_address
    account: EvmServerAccount | None = None

    if not address:
        if agent_data.cdp_wallet_data:
            wallet_data = json.loads(agent_data.cdp_wallet_data)
            if not isinstance(wallet_data, dict):
                raise ValueError("Invalid wallet data format")
            if wallet_data.get("default_address_id") and wallet_data.get("seed"):
                keys = bip39_seed_to_eth_keys(wallet_data["seed"])
                if keys["address"] != wallet_data["default_address_id"]:
                    raise ValueError(
                        "Bad wallet data, seed does not match default_address_id"
                    )
                logger.info("Migrating wallet data to v2...")
                account = await cdp_client.evm.import_account(
                    name=agent.id,
                    private_key=keys["private_key"],
                )
                address = account.address
                logger.info("Migrated wallet data to v2 successfully: %s", address)
        if not address:
            logger.info("Creating new wallet...")
            account = await cdp_client.evm.create_account(
                name=agent.id,
            )
            address = account.address
            logger.info("Created new wallet: %s", address)

        agent_data.evm_wallet_address = address
        await agent_data.save()
        if not agent.slug:
            async with get_session() as db:
                db_agent = await db.get(AgentTable, agent.id)
                if db_agent and not db_agent.slug:
                    db_agent.slug = agent_data.evm_wallet_address
                    await db.commit()

    if account is None:
        account = await cdp_client.evm.get_account(address=address)

    return account, agent_data


async def get_evm_account(agent: Agent) -> EvmServerAccount:
    _assert_cdp_wallet_provider(agent)
    account, _ = await _ensure_evm_account(agent)
    return account


async def get_wallet_provider(agent: Agent) -> CdpEvmWalletProvider:
    _assert_cdp_wallet_provider(agent)
    if not agent.network_id:
        raise IntentKitAPIError(
            400,
            "BadNetworkID",
            "Your agent network ID is not set. Please set it in the agent config.",
        )

    agent_data = await AgentData.get(agent.id)
    address = agent_data.evm_wallet_address

    cache_entry = _wallet_providers.get(agent.id)
    if cache_entry:
        cached_network_id, cached_address, provider = cache_entry
        if cached_network_id == agent.network_id:
            if not address:
                address = cached_address or provider.get_address()
            if cached_address == address:
                return provider

    account, agent_data = await _ensure_evm_account(agent, agent_data)
    address = account.address

    # Get credentials from global config
    api_key_id = config.cdp_api_key_id
    api_key_secret = config.cdp_api_key_secret
    wallet_secret = config.cdp_wallet_secret

    network_id = agent.network_id

    wallet_provider_config = CdpEvmWalletProviderConfig(
        api_key_id=api_key_id,
        api_key_secret=api_key_secret,
        network_id=network_id,
        address=address,
        wallet_secret=wallet_secret,
    )
    wallet_provider = await asyncio.to_thread(
        CdpEvmWalletProvider, wallet_provider_config
    )
    _wallet_providers[agent.id] = (network_id, address, wallet_provider)
    return wallet_provider
