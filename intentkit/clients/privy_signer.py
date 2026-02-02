import asyncio
import logging
import threading
from typing import Any

from eth_account.datastructures import SignedMessage
from eth_utils import keccak, to_checksum_address
from hexbytes import HexBytes

from intentkit.clients.privy_client import PrivyClient

logger = logging.getLogger(__name__)


# =============================================================================
# Privy Wallet Signer (eth_account compatible)
# =============================================================================


class PrivyWalletSigner:
    """
    EVM wallet signer that adapts Privy's API to eth_account interface.

    This allows Privy wallets to be used with libraries expecting
    standard EVM signer interfaces (like x402, web3.py, etc.).

    The signer uses the Privy EOA for signing, which is the actual
    key holder.

    Note: This class uses threading to run async Privy API calls
    synchronously, avoiding nested event loop issues when called
    from within an existing async context.
    """

    def __init__(
        self,
        privy_client: PrivyClient,
        wallet_id: str,
        wallet_address: str,
    ) -> None:
        """
        Initialize the Privy wallet signer.

        Args:
            privy_client: The Privy client for API calls.
            wallet_id: The Privy wallet ID.
            wallet_address: The EOA wallet address (used for signing).
        """
        self.privy_client = privy_client
        self.wallet_id = wallet_id
        self._signer_address = to_checksum_address(wallet_address)

    @property
    def address(self) -> str:
        """The Privy EOA address used for signing transactions."""
        return self._signer_address

    @property
    def signer_address(self) -> str:
        """The actual signer address (Privy EOA used for signing)."""
        return self._signer_address

    def _run_in_thread(self, coro: Any) -> Any:
        """
        Run an async coroutine in a separate thread.

        This avoids nested event loop errors when called from
        within an existing async context.

        Args:
            coro: The coroutine to run.

        Returns:
            The result of the coroutine.

        Raises:
            Any exception raised by the coroutine.
        """
        result: list[Any] = []
        error: list[BaseException] = []

        def _target() -> None:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result.append(loop.run_until_complete(coro))
                finally:
                    loop.close()
            except BaseException as exc:
                error.append(exc)

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join()

        if error:
            raise error[0]
        return result[0] if result else None

    def sign_message(self, signable_message: Any) -> Any:
        """
        Sign a message (EIP-191 personal_sign).

        Args:
            signable_message: The message to sign. Can be:
                - A string message
                - An eth_account.messages.SignableMessage
                - A bytes object

        Returns:
            SignedMessage-like object with v, r, s, and signature attributes.
        """
        # Handle different message types
        if hasattr(signable_message, "body"):
            # It's a SignableMessage, extract the body
            message_text = signable_message.body.decode("utf-8")
        elif isinstance(signable_message, bytes):
            message_text = signable_message.decode("utf-8")
        elif isinstance(signable_message, str):
            message_text = signable_message
        else:
            # Try to convert to string
            message_text = str(signable_message)

        # Sign via Privy
        signature_hex = self._run_in_thread(
            self.privy_client.sign_message(self.wallet_id, message_text)
        )

        # Parse the signature
        signature_bytes = bytes.fromhex(signature_hex.replace("0x", ""))

        # Extract v, r, s from signature
        r = int.from_bytes(signature_bytes[:32], "big")
        s = int.from_bytes(signature_bytes[32:64], "big")
        v = signature_bytes[64]

        # Create message hash for the SignedMessage
        message_bytes = message_text.encode("utf-8")
        prefix = f"\x19Ethereum Signed Message:\n{len(message_bytes)}".encode("utf-8")
        message_hash = keccak(prefix + message_bytes)

        return SignedMessage(
            message_hash=HexBytes(message_hash),
            r=r,
            s=s,
            v=v,
            signature=HexBytes(signature_bytes),
        )

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
            SignedMessage-like object with signature.
        """
        # Build the typed data structure
        if full_message is not None:
            typed_data = full_message
        else:
            # Infer primaryType from message_types keys (the first key that isn't EIP712Domain)
            # EIP-712 types dict contains type definitions, primaryType is NOT a key inside it
            primary_type = "Message"  # default fallback
            if message_types:
                for key in message_types:
                    if key != "EIP712Domain":
                        primary_type = key
                        break

            typed_data = {
                "domain": domain_data or {},
                "types": message_types or {},
                "message": message_data or {},
                "primaryType": primary_type,
            }

        # Sign via Privy
        signature_hex = self._run_in_thread(
            self.privy_client.sign_typed_data(self.wallet_id, typed_data)
        )

        # Parse the signature
        signature_bytes = bytes.fromhex(signature_hex.replace("0x", ""))

        # Extract v, r, s
        r = int.from_bytes(signature_bytes[:32], "big")
        s = int.from_bytes(signature_bytes[32:64], "big")
        v = signature_bytes[64]

        return SignedMessage(
            message_hash=HexBytes(b"\x00" * 32),
            r=r,
            s=s,
            v=v,
            signature=HexBytes(signature_bytes),
        )

    def unsafe_sign_hash(self, message_hash: Any) -> Any:
        """
        Sign a raw hash directly (unsafe, use with caution).

        This method signs a hash without any prefix or encoding.
        It uses personal_sign with the hex-encoded hash as the message.

        Args:
            message_hash: The 32-byte hash to sign. Can be bytes or HexBytes.

        Returns:
            SignedMessage-like object with signature.
        """
        # Convert to bytes if needed
        if hasattr(message_hash, "hex"):
            hash_bytes = bytes(message_hash)
        elif isinstance(message_hash, bytes):
            hash_bytes = message_hash
        else:
            hash_bytes = bytes.fromhex(str(message_hash).replace("0x", ""))

        # Sign via Privy using sign_hash
        signature_hex = self._run_in_thread(
            self.privy_client.sign_hash(self.wallet_id, hash_bytes)
        )

        # Parse the signature
        signature_bytes = bytes.fromhex(signature_hex.replace("0x", ""))

        # Extract v, r, s
        r = int.from_bytes(signature_bytes[:32], "big")
        s = int.from_bytes(signature_bytes[32:64], "big")
        v = signature_bytes[64]

        return SignedMessage(
            message_hash=HexBytes(hash_bytes),
            r=r,
            s=s,
            v=v,
            signature=HexBytes(signature_bytes),
        )

    def sign_transaction(self, transaction_dict: dict[str, Any]) -> Any:
        """
        Sign a transaction.

        Note: For Privy with Safe wallets, transactions are typically
        executed through the Safe rather than signed directly.
        This method is provided for interface compatibility.

        Args:
            transaction_dict: The transaction dictionary to sign.

        Returns:
            Signed transaction.

        Raises:
            NotImplementedError: Direct transaction signing is not supported.
                Use SafeWalletProvider.execute_transaction instead.
        """
        raise NotImplementedError(
            "Direct transaction signing is not supported for Privy wallets. "
            "Use SafeWalletProvider.execute_transaction() to execute transactions "
            "through the Safe smart account."
        )


def get_wallet_signer(
    privy_wallet_data: dict[str, Any],
) -> PrivyWalletSigner:
    """
    Create a PrivyWalletSigner from stored wallet data.

    This is used to get a signer for operations that require
    direct signing (like x402 payments).

    Args:
        privy_wallet_data: The stored wallet metadata containing
            privy_wallet_id and privy_wallet_address.

    Returns:
        PrivyWalletSigner instance ready for signing.
    """
    privy_client = PrivyClient()
    return PrivyWalletSigner(
        privy_client=privy_client,
        wallet_id=privy_wallet_data["privy_wallet_id"],
        wallet_address=privy_wallet_data["privy_wallet_address"],
    )
