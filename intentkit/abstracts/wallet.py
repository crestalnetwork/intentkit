"""
Unified wallet abstractions for on-chain skills.

This module defines abstract interfaces for wallet providers and signers,
allowing skills to work with different wallet implementations (CDP, Privy, etc.)
without knowing the specific implementation details.
"""

from abc import ABC, abstractmethod
from typing import Any


class UnifiedWalletProvider(ABC):
    """
    Abstract interface for wallet providers.

    This interface defines the common operations that any wallet provider
    (CDP, Privy/Safe, etc.) must implement to be used by on-chain skills.
    """

    @abstractmethod
    def get_address(self) -> str:
        """
        Get the wallet's public address (synchronous).

        Returns:
            The wallet address as a checksummed hex string.
        """
        pass

    @abstractmethod
    async def get_address_async(self) -> str:
        """
        Get the wallet's public address (asynchronous).

        Returns:
            The wallet address as a checksummed hex string.
        """
        pass

    @abstractmethod
    async def get_balance(self, chain_id: int | None = None) -> int:
        """
        Get native token balance in wei.

        Args:
            chain_id: Optional chain ID, uses default if not specified.

        Returns:
            Balance in wei as an integer.
        """
        pass

    @abstractmethod
    async def execute_transaction(
        self,
        to: str,
        value: int = 0,
        data: bytes = b"",
        chain_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Execute a transaction.

        Args:
            to: Destination address.
            value: Amount of native token to send (in wei).
            data: Transaction calldata.
            chain_id: Optional chain ID (uses default if not specified).

        Returns:
            Dict with 'success' (bool), 'tx_hash' (str), and optional 'error' (str).
        """
        pass


class UnifiedWalletSigner(ABC):
    """
    Abstract interface for EVM signers.

    This interface is compatible with eth_account's signing interfaces,
    allowing it to be used with libraries like x402 that expect standard
    EVM signers.
    """

    @property
    @abstractmethod
    def address(self) -> str:
        """
        The wallet address used for signing.

        Note: For Privy, this is the EOA address (not the Safe address),
        as signatures must come from the actual signer.
        """
        pass

    @abstractmethod
    def sign_message(self, signable_message: Any) -> Any:
        """
        Sign a message (EIP-191 personal_sign).

        Args:
            signable_message: The message to sign, typically an
                eth_account.messages.SignableMessage.

        Returns:
            The signature, typically as an eth_account SignedMessage or
            compatible object.
        """
        pass

    @abstractmethod
    def sign_transaction(self, transaction_dict: dict[str, Any]) -> Any:
        """
        Sign a transaction.

        Args:
            transaction_dict: The transaction dictionary to sign.

        Returns:
            The signed transaction.
        """
        pass

    @abstractmethod
    def sign_typed_data(
        self,
        domain_data: dict[str, Any] | None = None,
        message_types: dict[str, Any] | None = None,
        message_data: dict[str, Any] | None = None,
        full_message: dict[str, Any] | None = None,
    ) -> Any:
        """
        Sign typed data (EIP-712).

        Args:
            domain_data: The EIP-712 domain data.
            message_types: The type definitions.
            message_data: The message data to sign.
            full_message: Alternative: the complete typed data structure.

        Returns:
            The signature.
        """
        pass

    @abstractmethod
    def unsafe_sign_hash(self, message_hash: Any) -> Any:
        """
        Sign a raw hash directly (unsafe, use with caution).

        This method signs a hash without any prefix or encoding.
        It should only be used when you know exactly what you're signing.

        Args:
            message_hash: The 32-byte hash to sign.

        Returns:
            The signature.
        """
        pass
