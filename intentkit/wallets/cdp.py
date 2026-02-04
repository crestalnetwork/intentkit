import asyncio
import logging
from decimal import Decimal
from typing import Any, cast

from cdp import CdpClient, EvmServerAccount, TransactionRequestEIP1559
from eth_typing import HexStr
from web3 import Web3
from web3.types import TxParams, Wei

from intentkit.config.config import config
from intentkit.config.db import get_session
from intentkit.models.agent import Agent, AgentTable
from intentkit.models.agent_data import AgentData
from intentkit.utils.error import IntentKitAPIError
from intentkit.wallets.web3 import get_web3_client

_wallet_providers: dict[str, tuple[str, str, "CdpWalletProvider"]] = {}
_cdp_client: CdpClient | None = None

logger = logging.getLogger(__name__)


def _run_async(coroutine: Any) -> Any:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coroutine)
        finally:
            new_loop.close()

    return loop.run_until_complete(coroutine)


class CdpWalletProvider:
    """CDP SDK backed wallet provider for unified on-chain skills."""

    def __init__(
        self,
        cdp_client: CdpClient,
        account: EvmServerAccount,
        network: str,
        web3_client: Web3,
    ) -> None:
        self._cdp_client = cdp_client
        self._account = account
        self._network = network
        self._web3 = web3_client

    def get_address(self) -> str:
        return self._account.address

    async def get_balance(self) -> int:
        checksum_address = Web3.to_checksum_address(self._account.address)
        return await asyncio.to_thread(self._web3.eth.get_balance, checksum_address)

    def send_transaction(self, tx_params: TxParams) -> str:
        to = tx_params.get("to")
        if not to:
            raise IntentKitAPIError(
                400,
                "BadTransaction",
                "Transaction 'to' address is required.",
            )

        data = tx_params.get("data", "0x")
        if isinstance(data, bytes):
            data_hex = "0x" + data.hex()
        else:
            data_hex = str(data)
            if not data_hex.startswith("0x"):
                data_hex = f"0x{data_hex}"

        value = tx_params.get("value", Wei(0))
        try:
            value_int = int(value)
        except (TypeError, ValueError):
            value_int = 0

        request = TransactionRequestEIP1559(
            to=Web3.to_checksum_address(str(to)),
            value=value_int,
            data=cast(HexStr, data_hex),
        )

        result = _run_async(
            self._cdp_client.evm.send_transaction(
                address=self._account.address,
                transaction=request,
                network=self._network,
            )
        )

        if isinstance(result, str):
            return result
        if hasattr(result, "transaction_hash"):
            return str(result.transaction_hash)
        if isinstance(result, dict) and "transaction_hash" in result:
            return str(result["transaction_hash"])
        return str(result)

    async def wait_for_transaction_receipt(
        self,
        tx_hash: str,
        timeout: float = 120,
        poll_interval: float = 1.0,
    ) -> dict[str, Any]:
        receipt = await asyncio.to_thread(
            self._web3.eth.wait_for_transaction_receipt,
            cast(HexStr, tx_hash),
            timeout=timeout,
            poll_latency=poll_interval,
        )
        return dict(receipt)

    async def read_contract(
        self,
        contract_address: str,
        abi: list[dict[str, Any]],
        function_name: str,
        args: list[Any] | None = None,
    ) -> Any:
        contract = self._web3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=abi,
        )
        func = getattr(contract.functions, function_name)
        return await asyncio.to_thread(func(*(args or [])).call)

    def native_transfer(self, to: str, value: Decimal) -> str:
        value_wei = int(value * Decimal(10**18))
        tx_params: TxParams = {
            "to": Web3.to_checksum_address(to),
            "value": Wei(value_wei),
            "data": cast(HexStr, cast(object, "0x")),
        }
        return self.send_transaction(tx_params)


def get_cdp_client() -> CdpClient:
    global _cdp_client
    if _cdp_client:
        return _cdp_client

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
) -> tuple[EvmServerAccount, AgentData]:
    cdp_client = get_cdp_client()
    agent_data = agent_data or await AgentData.get(agent.id)
    address = agent_data.evm_wallet_address
    account: EvmServerAccount | None = None

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


def get_cdp_network(agent: Agent) -> str:
    if not agent.network_id:
        raise IntentKitAPIError(
            400,
            "BadNetworkID",
            "Your agent network ID is not set. Please set it in the agent config.",
        )
    mapping = {
        "ethereum-mainnet": "ethereum",
        "base-mainnet": "base",
        "arbitrum-mainnet": "arbitrum",
        "optimism-mainnet": "optimism",
        "polygon-mainnet": "polygon",
        "base-sepolia": "base-sepolia",
        "bnb-mainnet": "bsc",
    }
    if agent.network_id == "solana":
        raise IntentKitAPIError(
            400, "BadNetworkID", "Solana is not supported by CDP EVM."
        )
    cdp_network = mapping.get(agent.network_id)
    if not cdp_network:
        raise IntentKitAPIError(
            400, "BadNetworkID", f"Unsupported network ID: {agent.network_id}"
        )
    return cdp_network


async def get_wallet_provider(agent: Agent) -> CdpWalletProvider:
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

    cdp_client = get_cdp_client()
    cdp_network = get_cdp_network(agent)
    network_id = agent.network_id

    wallet_provider = CdpWalletProvider(
        cdp_client=cdp_client,
        account=account,
        network=cdp_network,
        web3_client=get_web3_client(network_id),
    )
    _wallet_providers[agent.id] = (network_id, address, wallet_provider)
    return wallet_provider


__all__ = [
    "CdpWalletProvider",
    "get_cdp_client",
    "get_cdp_network",
    "get_evm_account",
    "get_wallet_provider",
]
