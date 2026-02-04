"""
Unified EVM wallet wrapper for on-chain skills.

This module provides a unified interface for EVM wallets that works with
both CDP and Safe/Privy wallet providers, enabling on-chain skills to
work regardless of the underlying wallet implementation.
"""

import asyncio
import inspect
import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from eth_typing import ChecksumAddress, HexStr
from web3 import Web3
from web3.types import TxParams, Wei

from intentkit.utils.error import IntentKitAPIError
from intentkit.wallets import get_wallet_provider
from intentkit.wallets.web3 import get_web3_client

if TYPE_CHECKING:
    from intentkit.models.agent import Agent

logger = logging.getLogger(__name__)


class EvmWallet:
    """
    Unified EVM wallet interface for on-chain skills.

    This class provides a consistent async interface for wallet operations,
    abstracting away the differences between CDP and Safe/Privy providers.

    Usage:
        wallet = await EvmWallet.create(agent)
        address = wallet.address
        balance = await wallet.get_balance()
        tx_hash = await wallet.send_transaction(to="0x...", value=1000)
    """

    _provider: Any
    _network_id: str
    _chain_id: int | None
    _address: str | None
    _w3: Web3

    def __init__(
        self,
        provider: Any,
        network_id: str,
        chain_id: int | None = None,
    ):
        """
        Initialize the unified wallet.

        Args:
            provider: The underlying wallet provider (CDP or Safe).
            network_id: The network identifier (e.g., 'base-mainnet').
            chain_id: The chain ID (optional, will be resolved from network_id).
        """
        self._provider = provider
        self._network_id = network_id
        self._chain_id = chain_id
        self._address = None
        self._w3 = get_web3_client(network_id)

    @classmethod
    async def create(cls, agent: "Agent") -> "EvmWallet":
        """
        Factory method to create a unified wallet for an agent.

        Args:
            agent: The agent to create a wallet for.

        Returns:
            A configured EvmWallet instance.

        Raises:
            IntentKitAPIError: If the wallet cannot be created.
        """
        if not agent.network_id:
            raise IntentKitAPIError(
                400,
                "NetworkNotConfigured",
                "Agent network_id is not configured",
            )

        provider = await get_wallet_provider(agent)

        w3 = get_web3_client(agent.network_id)
        try:
            chain_id = w3.eth.chain_id
        except Exception:
            chain_id = None

        wallet = cls(provider, agent.network_id, chain_id)

        address_result = provider.get_address()
        if inspect.iscoroutine(address_result):
            wallet._address = await address_result
        else:
            wallet._address = address_result

        return wallet

    @property
    def address(self) -> str:
        """
        Get the wallet address.

        Returns:
            The checksummed wallet address.
        """
        if self._address is None:
            raise ValueError(
                "Wallet address not initialized. Use create() factory method."
            )
        return self._address

    @property
    def network_id(self) -> str:
        """Get the network ID."""
        return self._network_id

    @property
    def chain_id(self) -> int | None:
        """Get the chain ID."""
        return self._chain_id

    @property
    def w3(self) -> Web3:
        """Get the Web3 instance for this network."""
        return self._w3

    async def get_balance(self) -> int:
        """
        Get the native token balance in wei.

        Returns:
            Balance in wei as an integer.
        """
        if hasattr(self._provider, "get_balance"):
            result = self._provider.get_balance()
            if inspect.iscoroutine(result):
                return await result
            return int(result)

        checksum_addr = Web3.to_checksum_address(self.address)
        return self._w3.eth.get_balance(cast(ChecksumAddress, checksum_addr))

    async def send_transaction(
        self,
        to: str,
        value: int = 0,
        data: str | bytes = b"",
    ) -> str:
        """
        Send a transaction.

        Args:
            to: Destination address.
            value: Amount of native token to send in wei.
            data: Transaction calldata (hex string or bytes).

        Returns:
            Transaction hash as a hex string.

        Raises:
            IntentKitAPIError: If the transaction fails.
        """
        if isinstance(data, bytes):
            data_hex = "0x" + data.hex() if data else "0x"
        else:
            data_hex = data if data else "0x"

        if hasattr(self._provider, "execute_transaction"):
            data_bytes = (
                bytes.fromhex(data_hex[2:])
                if data_hex.startswith("0x")
                else bytes.fromhex(data_hex)
            )

            result = await self._provider.execute_transaction(
                to=to,
                value=value,
                data=data_bytes,
                chain_id=self._chain_id,
            )

            if not result.success:
                raise IntentKitAPIError(
                    500,
                    "TransactionFailed",
                    result.error or "Transaction execution failed",
                )

            return result.tx_hash or ""

        tx_params: TxParams = {
            "to": Web3.to_checksum_address(to),
            "value": Wei(value),
            "data": cast(HexStr, data_hex),
        }
        try:
            return self._provider.send_transaction(tx_params)
        except Exception as e:
            raise IntentKitAPIError(
                500, "TransactionFailed", f"Failed to send transaction: {e}"
            ) from e

    async def call_contract(
        self,
        contract_address: str,
        abi: list[dict[str, Any]],
        function_name: str,
        args: list[Any] | None = None,
    ) -> Any:
        """
        Call a contract function (read-only).

        Args:
            contract_address: Contract address.
            abi: Contract ABI.
            function_name: Function name to call.
            args: Function arguments.

        Returns:
            The result of the contract call.
        """
        if hasattr(self._provider, "read_contract"):
            return await self._provider.read_contract(
                contract_address,
                abi,
                function_name,
                args,
            )

        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=abi,
        )
        func = getattr(contract.functions, function_name)
        return func(*(args or [])).call()

    async def native_transfer(self, to: str, value: Decimal) -> str:
        """
        Transfer native tokens.

        Args:
            to: Destination address.
            value: Amount to transfer in whole units (e.g. 0.1).

        Returns:
            Transaction hash.
        """
        if hasattr(self._provider, "native_transfer"):
            result = self._provider.native_transfer(to, value)
            if inspect.iscoroutine(result):
                return await result
            return str(result)

        value_wei = int(value * Decimal(10**18))
        return await self.send_transaction(to=to, value=value_wei)

    async def wait_for_receipt(
        self,
        tx_hash: str,
        timeout: float = 120,
        poll_interval: float = 1.0,
    ) -> dict[str, Any]:
        """
        Wait for a transaction receipt.

        Args:
            tx_hash: Transaction hash.
            timeout: Timeout in seconds.
            poll_interval: Poll interval in seconds.

        Returns:
            Receipt dictionary.
        """
        if hasattr(self._provider, "wait_for_transaction_receipt"):
            result = await self._provider.wait_for_transaction_receipt(
                tx_hash,
                timeout=timeout,
                poll_interval=poll_interval,
            )
            return dict(result)

        receipt = await asyncio.to_thread(
            self._w3.eth.wait_for_transaction_receipt,
            cast(HexStr, tx_hash),
            timeout=timeout,
            poll_latency=poll_interval,
        )
        return dict(receipt)


__all__ = ["EvmWallet"]
