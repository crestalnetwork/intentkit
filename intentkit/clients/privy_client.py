import base64
import hashlib
import logging
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from intentkit.clients.privy_types import PrivyWallet
from intentkit.clients.privy_utils import (
    _canonicalize_json,
    _convert_typed_data_to_privy_format,
    _privy_private_key_to_pem,
    _sanitize_for_json,
)
from intentkit.config.config import config
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


# =============================================================================
# Privy Client
# =============================================================================


class PrivyClient:
    """Client for interacting with Privy Server Wallet API."""

    def __init__(self) -> None:
        self.app_id: str | None = config.privy_app_id
        self.app_secret: str | None = config.privy_app_secret
        self.base_url: str = config.privy_base_url
        self.authorization_private_keys: list[str] = (
            config.privy_authorization_private_keys
            if hasattr(config, "privy_authorization_private_keys")
            else []
        )
        self._authorization_key_objects: list[ec.EllipticCurvePrivateKey] = []
        self._authorization_key_fingerprints: list[str] = []

        for raw_key in self.authorization_private_keys:
            try:
                pem = _privy_private_key_to_pem(raw_key)
                key_obj = serialization.load_pem_private_key(pem, password=None)
                if not isinstance(key_obj, ec.EllipticCurvePrivateKey):
                    logger.warning(
                        "Privy authorization key ignored (not EC private key)"
                    )
                    continue
                if getattr(key_obj.curve, "name", "") != "secp256r1":
                    logger.warning(
                        "Privy authorization key curve unexpected: %s",
                        getattr(key_obj.curve, "name", ""),
                    )
                pub_der = key_obj.public_key().public_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                fp = hashlib.sha256(pub_der).hexdigest()[:16]
                self._authorization_key_objects.append(key_obj)
                self._authorization_key_fingerprints.append(fp)
            except Exception as exc:
                logger.warning("Failed to load Privy authorization key: %s", exc)

        if self.authorization_private_keys:
            logger.info(
                "Privy authorization keys loaded: configured=%s usable=%s fingerprints=%s",
                len(self.authorization_private_keys),
                len(self._authorization_key_objects),
                ",".join(self._authorization_key_fingerprints),
            )

        if not self.app_id or not self.app_secret:
            logger.warning("Privy credentials not configured")

    def _get_headers(self) -> dict[str, str]:
        return {
            "privy-app-id": self.app_id or "",
            "Content-Type": "application/json",
        }

    def get_authorization_public_keys(self) -> list[str]:
        """Get base64-encoded SPKI DER public keys for creating key quorums.

        These public keys can be used when creating a key quorum that includes
        the server's authorization key, enabling the server to sign requests
        for wallets owned by that key quorum.

        Returns:
            List of base64-encoded public keys in SPKI DER format.
        """
        public_keys = []
        for key_obj in self._authorization_key_objects:
            pub_der = key_obj.public_key().public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            public_keys.append(base64.b64encode(pub_der).decode("utf-8"))
        return public_keys

    def _get_authorization_signature(
        self, *, url: str, body: dict[str, Any], signed_headers: dict[str, str]
    ) -> str | None:
        if not self._authorization_key_objects:
            return None
        if not self.app_id:
            return None

        payload = {
            "version": 1,
            "method": "POST",
            "url": url,
            "body": body,
            "headers": signed_headers,
        }
        serialized_payload = _canonicalize_json(payload).encode("utf-8")
        payload_hash = hashlib.sha256(serialized_payload).hexdigest()[:16]
        logger.info("Privy auth payload sha256: %s", payload_hash)

        signatures: list[str] = []
        for private_key in self._authorization_key_objects:
            sig_bytes = private_key.sign(serialized_payload, ec.ECDSA(hashes.SHA256()))
            signatures.append(base64.b64encode(sig_bytes).decode("utf-8"))

        return ",".join(signatures) if signatures else None

    async def create_key_quorum(
        self,
        *,
        user_ids: list[str] | None = None,
        public_keys: list[str] | None = None,
        authorization_threshold: int | None = None,
        display_name: str | None = None,
    ) -> str:
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/key_quorums"
        payload: dict[str, Any] = {}
        if user_ids:
            payload["user_ids"] = user_ids
        if public_keys:
            payload["public_keys"] = public_keys
        if authorization_threshold is not None:
            payload["authorization_threshold"] = authorization_threshold
        if display_name:
            payload["display_name"] = display_name

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.app_id, self.app_secret),
                headers=self._get_headers(),
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    "Failed to create Privy key quorum",
                )

            data = response.json()
            return data["id"]

    async def create_wallet(
        self,
        owner_id: str | None = None,
        *,
        owner_user_id: str | None = None,
        owner_key_quorum_id: str | None = None,
        additional_signer_ids: list[str] | None = None,
    ) -> PrivyWallet:
        """Create a new server wallet.

        Args:
            owner_id: Deprecated alias for owner_user_id.
            owner_user_id: Optional Privy user ID to set as the wallet owner.
            owner_key_quorum_id: Optional key quorum ID to set as the wallet owner.
            additional_signer_ids: Optional key quorum IDs to add as additional signers.

        Note: Privy's create wallet API does not support idempotency keys.
        Idempotency keys are only supported for transaction APIs via the
        'privy-idempotency-key' HTTP header.
        """
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/wallets"
        payload: dict[str, Any] = {
            "chain_type": "ethereum",
        }
        effective_owner_user_id = owner_user_id or owner_id
        if effective_owner_user_id:
            payload["owner"] = {"user_id": effective_owner_user_id}
        if owner_key_quorum_id:
            payload["owner_id"] = owner_key_quorum_id
        if additional_signer_ids:
            payload["additional_signers"] = [
                {"signer_id": signer_id} for signer_id in additional_signer_ids
            ]

        headers = self._get_headers()
        authorization_signature = self._get_authorization_signature(
            url=url,
            body=payload,
            signed_headers={"privy-app-id": self.app_id or ""},
        )
        signature_count = (
            len([s for s in authorization_signature.split(",") if s.strip()])
            if authorization_signature
            else 0
        )
        if authorization_signature:
            headers["privy-authorization-signature"] = authorization_signature

        logger.info(
            "Privy create_wallet request: base_url=%s chain_type=%s owner_user_id=%s owner_key_quorum_id=%s additional_signers=%s auth_keys_configured=%s auth_sig_count=%s",
            self.base_url,
            payload.get("chain_type"),
            bool(effective_owner_user_id),
            bool(owner_key_quorum_id),
            len(additional_signer_ids or []),
            len(self.authorization_private_keys),
            signature_count,
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.app_id, self.app_secret),
                headers=headers,
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                logger.info(
                    "Privy create_wallet response: status=%s auth_sig_count=%s body=%s",
                    response.status_code,
                    signature_count,
                    response.text,
                )

                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    "Failed to create Privy wallet",
                )

            data = response.json()
            return PrivyWallet(
                id=data["id"],
                address=data["address"],
                chain_type=data["chain_type"],
            )

    async def get_wallet(self, wallet_id: str) -> PrivyWallet:
        """Get a specific wallet by ID."""
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/wallets/{wallet_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                auth=(self.app_id, self.app_secret),
                headers=self._get_headers(),
                timeout=30.0,
            )

            if response.status_code != 200:
                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    f"Failed to get Privy wallet {wallet_id}",
                )

            data = response.json()
            return PrivyWallet(
                id=data["id"],
                address=data["address"],
                chain_type=data["chain_type"],
            )

    async def sign_message(self, wallet_id: str, message: str) -> str:
        """Sign a message using the Privy server wallet.

        Uses personal_sign which signs the message with Ethereum's
        personal_sign prefix: "\\x19Ethereum Signed Message:\\n" + len(message) + message
        """
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/wallets/{wallet_id}/rpc"
        payload = {
            "method": "personal_sign",
            "params": {
                "message": message,
                "encoding": "utf-8",
            },
        }
        headers = self._get_headers()
        authorization_signature = self._get_authorization_signature(
            url=url,
            body=payload,
            signed_headers={"privy-app-id": self.app_id or ""},
        )
        signature_count = (
            len([s for s in authorization_signature.split(",") if s.strip()])
            if authorization_signature
            else 0
        )
        if authorization_signature:
            headers["privy-authorization-signature"] = authorization_signature

        logger.info(
            "Privy rpc request: wallet_id=%s method=%s base_url=%s auth_keys_configured=%s auth_sig_count=%s",
            wallet_id,
            payload.get("method"),
            self.base_url,
            len(self.authorization_private_keys),
            signature_count,
        )
        if self._authorization_key_fingerprints:
            logger.info(
                "Privy rpc auth fingerprints: %s",
                ",".join(self._authorization_key_fingerprints),
            )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.app_id, self.app_secret),
                headers=headers,
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                logger.info(
                    "Privy rpc response: wallet_id=%s method=%s status=%s auth_sig_count=%s body=%s",
                    wallet_id,
                    payload.get("method"),
                    response.status_code,
                    signature_count,
                    response.text,
                )

                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    "Failed to sign message with Privy wallet",
                )

            data = response.json()
            return data["data"]["signature"]

    async def sign_hash(self, wallet_id: str, hash_bytes: bytes) -> str:
        """Sign a raw hash directly using the Privy server wallet.

        Uses secp256k1_sign which signs the raw hash without any prefix.
        This is different from personal_sign which adds Ethereum's message prefix.
        """
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        # Privy expects the hash as a hex string with 0x prefix
        hash_hex = "0x" + hash_bytes.hex()

        url = f"{self.base_url}/wallets/{wallet_id}/rpc"
        payload = {
            "method": "secp256k1_sign",
            "params": {
                "hash": hash_hex,
            },
        }
        headers = self._get_headers()
        authorization_signature = self._get_authorization_signature(
            url=url,
            body=payload,
            signed_headers={"privy-app-id": self.app_id or ""},
        )
        signature_count = (
            len([s for s in authorization_signature.split(",") if s.strip()])
            if authorization_signature
            else 0
        )
        if authorization_signature:
            headers["privy-authorization-signature"] = authorization_signature

        logger.info(
            "Privy rpc request: wallet_id=%s method=%s base_url=%s auth_keys_configured=%s auth_sig_count=%s",
            wallet_id,
            payload.get("method"),
            self.base_url,
            len(self.authorization_private_keys),
            signature_count,
        )
        if self._authorization_key_fingerprints:
            logger.info(
                "Privy rpc auth fingerprints: %s",
                ",".join(self._authorization_key_fingerprints),
            )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.app_id, self.app_secret),
                headers=headers,
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                logger.info(
                    "Privy rpc response: wallet_id=%s method=%s status=%s auth_sig_count=%s body=%s",
                    wallet_id,
                    payload.get("method"),
                    response.status_code,
                    signature_count,
                    response.text,
                )

                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    "Failed to sign hash with Privy wallet",
                )

            data = response.json()
            return data["data"]["signature"]

    async def sign_typed_data(self, wallet_id: str, typed_data: dict[str, Any]) -> str:
        """Sign typed data (EIP-712) using the Privy server wallet."""
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/wallets/{wallet_id}/rpc"
        # Convert typed_data to Privy format (primaryType -> primary_type)
        # then sanitize to convert bytes to hex strings for JSON serialization
        privy_typed_data = _convert_typed_data_to_privy_format(typed_data)
        sanitized_typed_data = _sanitize_for_json(privy_typed_data)
        payload = {
            "method": "eth_signTypedData_v4",
            "params": {
                "typed_data": sanitized_typed_data,
            },
        }
        headers = self._get_headers()
        authorization_signature = self._get_authorization_signature(
            url=url,
            body=payload,
            signed_headers={"privy-app-id": self.app_id or ""},
        )
        signature_count = (
            len([s for s in authorization_signature.split(",") if s.strip()])
            if authorization_signature
            else 0
        )
        if authorization_signature:
            headers["privy-authorization-signature"] = authorization_signature

        logger.info(
            "Privy rpc request: wallet_id=%s method=%s base_url=%s auth_keys_configured=%s auth_sig_count=%s",
            wallet_id,
            payload.get("method"),
            self.base_url,
            len(self.authorization_private_keys),
            signature_count,
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.app_id, self.app_secret),
                headers=headers,
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                logger.info(
                    "Privy rpc response: wallet_id=%s method=%s status=%s auth_sig_count=%s body=%s",
                    wallet_id,
                    payload.get("method"),
                    response.status_code,
                    signature_count,
                    response.text,
                )

                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    "Failed to sign typed data with Privy wallet",
                )

            data = response.json()
            return data["data"]["signature"]

    async def send_transaction(
        self,
        wallet_id: str,
        chain_id: int,
        to: str,
        value: int = 0,
        data: str = "0x",
    ) -> str:
        """Send a transaction using the Privy server wallet."""
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/wallets/{wallet_id}/rpc"
        payload = {
            "method": "eth_sendTransaction",
            "caip2": f"eip155:{chain_id}",
            "params": {
                "transaction": {
                    "to": to,
                    "value": hex(value),
                    "data": data,
                }
            },
        }

        headers = self._get_headers()
        authorization_signature = self._get_authorization_signature(
            url=url,
            body=payload,
            signed_headers={"privy-app-id": self.app_id or ""},
        )
        signature_count = (
            len([s for s in authorization_signature.split(",") if s.strip()])
            if authorization_signature
            else 0
        )
        if authorization_signature:
            headers["privy-authorization-signature"] = authorization_signature

        logger.info(
            "Privy rpc request: wallet_id=%s method=%s base_url=%s auth_keys_configured=%s auth_sig_count=%s",
            wallet_id,
            payload.get("method"),
            self.base_url,
            len(self.authorization_private_keys),
            signature_count,
        )
        if self._authorization_key_fingerprints:
            logger.info(
                "Privy rpc auth fingerprints: %s",
                ",".join(self._authorization_key_fingerprints),
            )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.app_id, self.app_secret),
                headers=headers,
                timeout=60.0,
            )

            if response.status_code not in (200, 201):
                logger.info(
                    "Privy rpc response: wallet_id=%s method=%s status=%s auth_sig_count=%s body=%s",
                    wallet_id,
                    payload.get("method"),
                    response.status_code,
                    signature_count,
                    response.text,
                )

                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    f"Failed to send transaction: {response.text}",
                )

            data_response = response.json()
            return data_response["data"]["hash"]
