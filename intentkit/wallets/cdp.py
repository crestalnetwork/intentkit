import logging
from decimal import Decimal
from typing import Any, cast

from cdp import CdpClient, EvmServerAccount, TransactionRequestEIP1559
from eth_typing import HexStr
from web3 import AsyncWeb3
from web3.types import TxParams, Wei

from intentkit.config.config import config
from intentkit.models.wallet import TeamWallet
from intentkit.utils.error import IntentKitAPIError
from intentkit.wallets.web3 import get_async_web3_client

# Keyed by (wallet id, network, address): wallets are shared across agents
# and networks, and the address guard drops stale entries if a wallet row is
# ever re-pointed at a different account.
_wallet_providers: dict[tuple[str, str, str], "CdpWalletProvider"] = {}
_cdp_client: CdpClient | None = None

logger = logging.getLogger(__name__)


class CdpWalletProvider:
    """CDP SDK backed wallet provider for unified on-chain tools."""

    _cdp_client: CdpClient
    _account: EvmServerAccount
    _network: str
    _web3: AsyncWeb3

    def __init__(
        self,
        cdp_client: CdpClient,
        account: EvmServerAccount,
        network: str,
        web3_client: AsyncWeb3,
    ) -> None:
        self._cdp_client = cdp_client
        self._account = account
        self._network = network
        self._web3 = web3_client

    def get_address(self) -> str:
        return self._account.address

    async def get_balance(self) -> int:
        checksum_address = AsyncWeb3.to_checksum_address(self._account.address)
        return await self._web3.eth.get_balance(checksum_address)

    async def send_transaction(self, tx_params: TxParams) -> str:
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
            to=AsyncWeb3.to_checksum_address(str(to)),
            value=value_int,
            data=cast(HexStr, data_hex),
        )

        result = await self._cdp_client.evm.send_transaction(
            address=self._account.address,
            transaction=request,
            network=self._network,
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
        receipt = await self._web3.eth.wait_for_transaction_receipt(
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
            address=AsyncWeb3.to_checksum_address(contract_address),
            abi=abi,
        )
        func = getattr(contract.functions, function_name)
        return await func(*(args or [])).call()

    async def native_transfer(self, to: str, value: Decimal) -> str:
        value_wei = int(value * Decimal(10**18))
        tx_params: TxParams = {
            "to": AsyncWeb3.to_checksum_address(to),
            "value": Wei(value_wei),
            "data": cast(HexStr, cast(object, "0x")),
        }
        return await self.send_transaction(tx_params)


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


def _assert_cdp_wallet(wallet: TeamWallet) -> None:
    if wallet.wallet_provider != "cdp":
        raise IntentKitAPIError(
            400,
            "BadWalletProvider",
            "The bound wallet is not a CDP wallet but you selected a tool that requires one.",
        )


async def get_evm_account(wallet: TeamWallet) -> EvmServerAccount:
    _assert_cdp_wallet(wallet)
    if not wallet.evm_wallet_address:
        raise IntentKitAPIError(
            400,
            "CdpWalletNotInitialized",
            f"CDP wallet {wallet.id} has no address.",
        )
    cdp_client = get_cdp_client()
    return await cdp_client.evm.get_account(address=wallet.evm_wallet_address)


def get_cdp_network(network_id: str | None) -> str:
    if not network_id:
        raise IntentKitAPIError(
            400,
            "BadNetworkID",
            "No network is configured for this wallet.",
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
    if network_id == "solana":
        raise IntentKitAPIError(
            400, "BadNetworkID", "Solana is not supported by CDP EVM."
        )
    cdp_network = mapping.get(network_id)
    if not cdp_network:
        raise IntentKitAPIError(
            400, "BadNetworkID", f"Unsupported network ID: {network_id}"
        )
    return cdp_network


async def get_wallet_provider(wallet: TeamWallet) -> CdpWalletProvider:
    _assert_cdp_wallet(wallet)
    network_id = wallet.network

    cache_key = (wallet.id, network_id, wallet.evm_wallet_address or "")
    cached = _wallet_providers.get(cache_key)
    if cached:
        return cached

    account = await get_evm_account(wallet)

    wallet_provider = CdpWalletProvider(
        cdp_client=get_cdp_client(),
        account=account,
        network=get_cdp_network(network_id),
        web3_client=get_async_web3_client(network_id),
    )
    _wallet_providers[cache_key] = wallet_provider
    return wallet_provider


async def close_cdp_client() -> None:
    """Close the global CDP client if it exists."""
    global _cdp_client
    if _cdp_client is not None:
        await _cdp_client.close()
        _cdp_client = None


__all__ = [
    "CdpWalletProvider",
    "close_cdp_client",
    "get_cdp_client",
    "get_cdp_network",
    "get_evm_account",
    "get_wallet_provider",
]
