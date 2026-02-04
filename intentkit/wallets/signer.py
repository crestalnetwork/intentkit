"""
CDP EVM wallet signer wrapper using EvmLocalAccount.

This module provides a lightweight signer wrapper around CDP SDK's
EvmLocalAccount so callers can sign messages and transactions using
a consistent interface.
"""

from typing import Any

from cdp import EvmLocalAccount, EvmServerAccount


class ThreadSafeEvmWalletSigner:
    """
    EVM wallet signer wrapper backed by EvmLocalAccount.

    This keeps the same public interface expected by the rest of the codebase
    while delegating to CDP SDK's EvmLocalAccount for signing.
    """

    def __init__(self, server_account: EvmServerAccount) -> None:
        """
        Initialize the signer.

        Args:
            server_account: The CDP EVM server account to sign with.
        """
        self._account = EvmLocalAccount(server_account)

    @property
    def address(self) -> str:
        """Get the wallet address."""
        return self._account.address

    def unsafe_sign_hash(self, message_hash: Any) -> Any:
        """Sign a hash directly (unsafe)."""
        return self._account.unsafe_sign_hash(message_hash)

    def sign_message(self, signable_message: Any) -> Any:
        """Sign a message (EIP-191)."""
        return self._account.sign_message(signable_message)

    def sign_transaction(self, transaction_dict: Any) -> Any:
        """Sign a transaction."""
        return self._account.sign_transaction(transaction_dict)

    def sign_typed_data(
        self,
        domain_data: Any | None = None,
        message_types: Any | None = None,
        message_data: Any | None = None,
        full_message: Any | None = None,
    ) -> Any:
        """Sign typed data (EIP-712)."""
        return self._account.sign_typed_data(
            domain_data=domain_data,
            message_types=message_types,
            message_data=message_data,
            full_message=full_message,
        )


__all__ = ["EvmLocalAccount", "ThreadSafeEvmWalletSigner"]
