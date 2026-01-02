"""
Thread-safe EVM wallet signer wrappers.

This module provides thread-safe wrappers for EVM wallet signers,
allowing them to be used from within async contexts without
running into nested event loop issues.
"""

import threading
from typing import Any


class ThreadSafeEvmWalletSigner:
    """
    EVM wallet signer that avoids nested event loop errors.

    Coinbase's signer runs async wallet calls in the current thread. When invoked
    inside an active asyncio loop (as happens in async skills), it trips over the
    loop already running. We hop work to a background thread so the provider can
    spin up its own loop safely.

    This wrapper is used with CdpEvmWalletProvider to provide signing capabilities
    that are compatible with libraries like x402.
    """

    def __init__(self, wallet_provider: Any) -> None:
        """
        Initialize the thread-safe signer.

        Args:
            wallet_provider: The CDP wallet provider to wrap.
                Expected to be a CdpEvmWalletProvider instance.
        """
        # Import here to avoid issues if coinbase_agentkit is not installed
        from coinbase_agentkit.wallet_providers.evm_wallet_provider import (
            EvmWalletSigner as CoinbaseEvmWalletSigner,
        )

        # Create the underlying signer
        self._inner_signer = CoinbaseEvmWalletSigner(wallet_provider=wallet_provider)
        self._wallet_provider = wallet_provider

    @property
    def address(self) -> str:
        """Get the wallet address."""
        return self._wallet_provider.get_address()

    def _run_in_thread(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """
        Run a function in a separate thread.

        This avoids nested event loop errors when the underlying
        function needs to run async code.

        Args:
            func: The function to call.
            *args: Positional arguments to pass.
            **kwargs: Keyword arguments to pass.

        Returns:
            The result of the function call.

        Raises:
            Any exception raised by the function.
        """
        result: list[Any] = []
        error: list[BaseException] = []

        def _target() -> None:
            try:
                result.append(func(*args, **kwargs))
            except BaseException as exc:
                error.append(exc)

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join()

        if error:
            raise error[0]
        return result[0] if result else None

    def unsafe_sign_hash(self, message_hash: Any) -> Any:
        """
        Sign a hash directly (unsafe).

        Args:
            message_hash: The hash to sign.

        Returns:
            The signature.
        """
        return self._run_in_thread(self._inner_signer.unsafe_sign_hash, message_hash)

    def sign_message(self, signable_message: Any) -> Any:
        """
        Sign a message (EIP-191).

        Args:
            signable_message: The message to sign.

        Returns:
            The signed message.
        """
        return self._run_in_thread(self._inner_signer.sign_message, signable_message)

    def sign_transaction(self, transaction_dict: Any) -> Any:
        """
        Sign a transaction.

        Args:
            transaction_dict: The transaction to sign.

        Returns:
            The signed transaction.
        """
        return self._run_in_thread(
            self._inner_signer.sign_transaction, transaction_dict
        )

    def sign_typed_data(
        self,
        domain_data: Any | None = None,
        message_types: Any | None = None,
        message_data: Any | None = None,
        full_message: Any | None = None,
    ) -> Any:
        """
        Sign typed data (EIP-712).

        Args:
            domain_data: The EIP-712 domain data.
            message_types: The type definitions.
            message_data: The message data.
            full_message: Alternative: the complete typed data structure.

        Returns:
            The signature.
        """
        return self._run_in_thread(
            self._inner_signer.sign_typed_data,
            domain_data=domain_data,
            message_types=message_types,
            message_data=message_data,
            full_message=full_message,
        )
