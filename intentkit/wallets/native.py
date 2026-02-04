"""Native wallet provider implementation.

This module provides a native wallet provider that generates wallets directly
using web3/eth_account, storing the private key in the agent_data table.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from eth_account import Account
from eth_account.datastructures import SignedMessage, SignedTransaction
from eth_account.messages import SignableMessage
from hexbytes import HexBytes
from web3 import Web3
from web3.types import TxParams, Wei

from intentkit.utils.error import IntentKitAPIError
from intentkit.wallets.web3 import get_web3_client

logger = logging.getLogger(__name__)


@dataclass
class TransactionResult:
    """Result of a transaction execution."""

    success: bool
    tx_hash: str | None = None
    error: str | None = None


class NativeWalletProvider:
    """Native wallet provider using locally stored private keys.

        This provider generates wallets directly using eth_account and stores
    the encrypted private key in the agent_data table. It uses web3 for all
        on-chain operations.
    """

    def __init__(
        self,
        address: str,
        private_key: str,
        network_id: str,
    ) -> None:
        """Initialize the native wallet provider.

        Args:
            address: The wallet address.
            private_key: The private key (hex string with 0x prefix).
            network_id: The network identifier (e.g., 'base-mainnet').
        """
        self._address = Web3.to_checksum_address(address)
        self._private_key = private_key
        self._network_id = network_id
        self._account = Account.from_key(private_key)
        self._w3 = get_web3_client(network_id)

    def get_address(self) -> str:
        """Get the wallet's public address."""
        return self._address

    async def get_address_async(self) -> str:
        """Get the wallet's public address (async version)."""
        return self._address

    async def get_balance(self, chain_id: int | None = None) -> int:
        """Get native token balance in wei."""
        return self._w3.eth.get_balance(self._address)

    async def execute_transaction(
        self,
        to: str,
        value: int = 0,
        data: bytes = b"",
        chain_id: int | None = None,
    ) -> TransactionResult:
        """Execute a transaction.

        Args:
            to: Destination address.
            value: Amount of native token to send (in wei).
            data: Transaction calldata.
            chain_id: Optional chain ID (uses default if not specified).

        Returns:
            TransactionResult with success status and tx hash.
        """
        try:
            nonce = self._w3.eth.get_transaction_count(self._address)

            tx_params: TxParams = {
                "nonce": nonce,
                "to": Web3.to_checksum_address(to),
                "value": Wei(value),
                "data": HexBytes(data) if data else b"",
                "chainId": chain_id or self._w3.eth.chain_id,
                "gas": 21000,
            }
            if data:
                try:
                    tx_params["gas"] = Wei(self._w3.eth.estimate_gas(tx_params))
                except Exception as e:
                    logger.warning(f"Gas estimation failed, using default: {e}")
                    tx_params["gas"] = Wei(100000)

            try:
                fee_history = self._w3.eth.fee_history(1, "latest")
                base_fee = fee_history["baseFeePerGas"][0]
                tx_params["maxFeePerGas"] = Wei(int(base_fee * 2))
                tx_params["maxPriorityFeePerGas"] = Wei(int(base_fee * 0.1))
            except Exception as e:
                logger.warning(f"Failed to get fee history, using legacy gas: {e}")
                tx_params["gasPrice"] = Wei(self._w3.eth.gas_price)

            signed_tx = self._account.sign_transaction(tx_params)
            tx_hash = self._w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            return TransactionResult(
                success=True,
                tx_hash=tx_hash.hex()
                if isinstance(tx_hash, HexBytes)
                else str(tx_hash),
            )

        except Exception as e:
            logger.error(f"Transaction execution failed: {e}")
            return TransactionResult(success=False, error=str(e))

    async def transfer_erc20(
        self,
        token_address: str,
        to: str,
        amount: int,
        chain_id: int | None = None,
    ) -> TransactionResult:
        """Transfer ERC20 tokens.

        Args:
            token_address: The token contract address.
            to: Recipient address.
            amount: Amount to transfer (in token's smallest unit).
            chain_id: Optional chain ID.

        Returns:
            TransactionResult with success status and tx hash.
        """
        erc20_abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"},
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function",
            }
        ]

        try:
            contract = self._w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=erc20_abi,
            )

            data = contract.functions.transfer(
                Web3.to_checksum_address(to),
                amount,
            ).build_transaction(
                {
                    "from": self._address,
                    "nonce": self._w3.eth.get_transaction_count(self._address),
                    "chainId": chain_id or self._w3.eth.chain_id,
                }
            )

            tx_data = data.get("data", b"")

            return await self.execute_transaction(
                to=token_address,
                value=0,
                data=tx_data
                if isinstance(tx_data, bytes)
                else bytes.fromhex(tx_data[2:]),
                chain_id=chain_id,
            )

        except Exception as e:
            logger.error(f"ERC20 transfer failed: {e}")
            return TransactionResult(success=False, error=str(e))

    async def get_erc20_balance(
        self,
        token_address: str,
        chain_id: int | None = None,
    ) -> int:
        """Get ERC20 token balance."""
        erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            }
        ]

        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=erc20_abi,
        )
        return contract.functions.balanceOf(self._address).call()

    def native_transfer(self, to: str, value: Decimal) -> str:
        """Transfer native tokens (ETH/MATIC/etc).

        Args:
            to: Destination address.
            value: Amount to transfer in whole units (e.g., 1.5 for 1.5 ETH).

        Returns:
            Transaction hash as a hex string.
        """
        import asyncio

        value_wei = int(value * Decimal(10**18))
        result = asyncio.run(
            self.execute_transaction(
                to=to,
                value=value_wei,
            )
        )
        if not result.success:
            raise IntentKitAPIError(
                500,
                "TransactionFailed",
                result.error or "Native transfer failed",
            )
        return result.tx_hash or ""


class NativeWalletSigner:
    """Native wallet signer compatible with eth_account interfaces."""

    def __init__(self, address: str, private_key: str) -> None:
        """Initialize the native wallet signer.

        Args:
            address: The wallet address.
            private_key: The private key (hex string with 0x prefix).
        """
        self._address = Web3.to_checksum_address(address)
        self._account = Account.from_key(private_key)

    @property
    def address(self) -> str:
        """Get the wallet address."""
        return self._address

    def sign_message(self, signable_message: SignableMessage) -> SignedMessage:
        """Sign a message (EIP-191 personal_sign).

        Args:
            signable_message: The message to sign.

        Returns:
            The signed message.
        """
        return self._account.sign_message(signable_message)

    def sign_transaction(self, transaction_dict: dict[str, Any]) -> SignedTransaction:
        """Sign a transaction.

        Args:
            transaction_dict: The transaction dictionary to sign.

        Returns:
            The signed transaction.
        """
        return self._account.sign_transaction(transaction_dict)

    def sign_typed_data(
        self,
        domain_data: dict[str, Any] | None = None,
        message_types: dict[str, Any] | None = None,
        message_data: dict[str, Any] | None = None,
        full_message: dict[str, Any] | None = None,
    ) -> SignedMessage:
        """Sign typed data (EIP-712).

        Args:
            domain_data: The EIP-712 domain data.
            message_types: The type definitions.
            message_data: The message data to sign.
            full_message: Alternative: the complete typed data structure.

        Returns:
            The signature.
        """
        from eth_account.messages import encode_typed_data

        if full_message:
            signable = encode_typed_data(full_message=full_message)
        else:
            signable = encode_typed_data(
                domain_data=domain_data,
                message_types=message_types,
                message_data=message_data,
            )
        return self._account.sign_message(signable)

    def unsafe_sign_hash(self, message_hash: HexBytes) -> SignedMessage:
        """Sign a raw hash directly (unsafe, use with caution).

        Args:
            message_hash: The 32-byte hash to sign.

        Returns:
            The signature.
        """
        return self._account.unsafe_sign_hash(message_hash)


def create_native_wallet(network_id: str) -> dict[str, str]:
    """Create a new native wallet.

    Args:
        network_id: The network identifier (e.g., 'base-mainnet').

    Returns:
        dict containing:
            - address: The wallet address.
            - private_key: The private key (hex string with 0x prefix).
            - network_id: The network ID.
    """
    account = Account.create()

    return {
        "address": account.address,
        "private_key": account.key.hex(),
        "network_id": network_id,
    }


def get_wallet_provider(
    native_wallet_data: dict[str, Any],
) -> NativeWalletProvider:
    """Create a NativeWalletProvider from stored wallet data.

    Args:
        native_wallet_data: The stored wallet metadata containing address,
            private_key, and network_id.

    Returns:
        NativeWalletProvider instance ready for transactions.
    """
    return NativeWalletProvider(
        address=native_wallet_data["address"],
        private_key=native_wallet_data["private_key"],
        network_id=native_wallet_data.get("network_id", "base-mainnet"),
    )


def get_wallet_signer(native_wallet_data: dict[str, Any]) -> NativeWalletSigner:
    """Create a NativeWalletSigner from stored wallet data.

    Args:
        native_wallet_data: The stored wallet metadata.

    Returns:
        NativeWalletSigner instance ready for signing.
    """
    return NativeWalletSigner(
        address=native_wallet_data["address"],
        private_key=native_wallet_data["private_key"],
    )


__all__ = [
    "NativeWalletProvider",
    "NativeWalletSigner",
    "TransactionResult",
    "create_native_wallet",
    "get_wallet_provider",
    "get_wallet_signer",
]
