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

from intentkit.clients import get_wallet_provider
from intentkit.clients.web3 import get_web3_client
from intentkit.utils.error import IntentKitAPIError

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

        # Get chain ID from Web3
        w3 = get_web3_client(agent.network_id)
        try:
            chain_id = w3.eth.chain_id
        except Exception:
            chain_id = None

        wallet = cls(provider, agent.network_id, chain_id)

        # Pre-fetch address
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
        # Check if provider has async get_balance (Safe/Privy)
        if hasattr(self._provider, "get_balance"):
            result = self._provider.get_balance()
            if inspect.iscoroutine(result):
                return await result
            return int(result)

        # Fallback to Web3 call
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
        # Normalize data to hex string
        if isinstance(data, bytes):
            data_hex = "0x" + data.hex() if data else "0x"
        else:
            data_hex = data if data else "0x"

        # Try Safe/Privy provider first (has execute_transaction)
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

        # CDP provider (has send_transaction that takes TxParams)
        if hasattr(self._provider, "send_transaction"):
            tx_params: TxParams = {
                "to": Web3.to_checksum_address(to),
                "data": HexStr(data_hex),
            }
            if value > 0:
                tx_params["value"] = Wei(value)

            if inspect.iscoroutinefunction(self._provider.send_transaction):
                tx_hash = await self._provider.send_transaction(tx_params)
            else:
                tx_hash = await asyncio.to_thread(
                    self._provider.send_transaction, tx_params
                )
            return str(tx_hash)

        raise IntentKitAPIError(
            500,
            "UnsupportedOperation",
            "Wallet provider does not support send_transaction",
        )

    async def wait_for_transaction_receipt(
        self,
        tx_hash: str,
        timeout: float = 120,
        poll_interval: float = 1.0,
    ) -> dict[str, Any]:
        """
        Wait for a transaction receipt.

        Args:
            tx_hash: The transaction hash to wait for.
            timeout: Maximum time to wait in seconds.
            poll_interval: Time between polls in seconds.

        Returns:
            The transaction receipt as a dict.
        """
        # Try provider method first
        if hasattr(self._provider, "wait_for_transaction_receipt"):
            result = self._provider.wait_for_transaction_receipt(
                tx_hash, timeout, poll_interval
            )
            if inspect.iscoroutine(result):
                return dict(await result)
            return dict(result)

        # Fallback to Web3
        receipt = await asyncio.to_thread(
            self._w3.eth.wait_for_transaction_receipt,
            HexStr(tx_hash),
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
        """
        Read from a smart contract.

        Args:
            contract_address: The contract address.
            abi: The contract ABI.
            function_name: The function to call.
            args: The function arguments.

        Returns:
            The function return value.
        """
        # Try provider method first (CDP has read_contract)
        if hasattr(self._provider, "read_contract"):
            result = self._provider.read_contract(
                contract_address=Web3.to_checksum_address(contract_address),
                abi=abi,
                function_name=function_name,
                args=args or [],
            )
            if inspect.iscoroutine(result):
                return await result
            return result

        # Fallback to Web3
        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=abi,
        )
        func = getattr(contract.functions, function_name)
        return await asyncio.to_thread(func(*(args or [])).call)

    async def native_transfer(
        self,
        to: str,
        value: Decimal,
    ) -> str:
        """
        Transfer native tokens (ETH/MATIC/etc).

        Args:
            to: Destination address.
            value: Amount to transfer in whole units (e.g., 1.5 for 1.5 ETH).

        Returns:
            Transaction hash as a hex string.
        """
        # Convert to wei
        value_wei = int(value * Decimal(10**18))

        # Try provider's native_transfer if available
        if hasattr(self._provider, "native_transfer"):
            if inspect.iscoroutinefunction(self._provider.native_transfer):
                return await self._provider.native_transfer(to, value)
            return await asyncio.to_thread(self._provider.native_transfer, to, value)

        # Fallback to send_transaction
        return await self.send_transaction(to=to, value=value_wei)

    def is_cdp_provider(self) -> bool:
        """Check if the underlying provider is a CDP provider."""
        provider_type = type(self._provider).__name__
        return "Cdp" in provider_type

    def is_safe_provider(self) -> bool:
        """Check if the underlying provider is a Safe/Privy provider."""
        provider_type = type(self._provider).__name__
        return "Safe" in provider_type or "Privy" in provider_type

    def get_raw_provider(self) -> Any:
        """
        Get the underlying wallet provider.

        This should only be used when provider-specific functionality is needed.
        """
        return self._provider
