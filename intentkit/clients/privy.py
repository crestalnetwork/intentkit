"""
Privy + Safe Smart Wallet Client

This module provides integration between Privy server wallets (EOA signers)
and Safe smart accounts for autonomous agent transactions.

Architecture:
- Privy provides the EOA (Externally Owned Account) as the signer/owner
- Safe provides the smart account with spending limits via Allowance Module
- The agent's public address is the Safe smart account address
- Transactions are signed by Privy and executed through Safe
"""

import base64
import hashlib
import json
import logging
import textwrap
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, cast

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from eth_abi import encode
from eth_account import Account
from eth_utils import keccak, to_checksum_address
from hexbytes import HexBytes
from pydantic import BaseModel
from web3 import AsyncWeb3
from web3.types import TxParams

from intentkit.config.config import config
from intentkit.config.redis import get_redis
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


def _canonicalize_json(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    if isinstance(value, str):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    # Handle bytes and HexBytes by converting to hex string
    if isinstance(value, (bytes, HexBytes)):
        hex_str = value.hex()
        if not hex_str.startswith("0x"):
            hex_str = f"0x{hex_str}"
        return json.dumps(hex_str, separators=(",", ":"), ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonicalize_json(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        parts: list[str] = []
        for k in keys:
            if not isinstance(k, str):
                raise TypeError("JSON object keys must be strings")
            parts.append(_canonicalize_json(k) + ":" + _canonicalize_json(value[k]))
        return "{" + ",".join(parts) + "}"
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _privy_private_key_to_pem(key: str) -> bytes:
    private_key_as_string = key.replace("wallet-auth:", "").strip()
    wrapped = "\n".join(textwrap.wrap(private_key_as_string, width=64))
    pem = f"-----BEGIN PRIVATE KEY-----\n{wrapped}\n-----END PRIVATE KEY-----\n"
    return pem.encode("utf-8")


def _sanitize_for_json(value: object) -> object:
    """Recursively convert bytes and HexBytes to hex strings for JSON serialization.

    This is needed when passing data structures to httpx's json= parameter,
    which uses standard json.dumps() that doesn't support bytes.
    """
    if isinstance(value, (bytes, HexBytes)):
        hex_str = value.hex()
        if not hex_str.startswith("0x"):
            hex_str = f"0x{hex_str}"
        return hex_str
    elif isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [_sanitize_for_json(item) for item in value]
    else:
        return value


def _convert_typed_data_to_privy_format(typed_data: dict[str, Any]) -> dict[str, Any]:
    """Convert EIP-712 typed data to Privy's expected format.

    Privy API expects snake_case field names but EIP-712 uses camelCase.
    Main conversion: primaryType -> primary_type
    """
    result = dict(typed_data)

    # Convert primaryType to primary_type
    if "primaryType" in result:
        result["primary_type"] = result.pop("primaryType")

    return result


# =============================================================================
# Chain Configuration
# =============================================================================


# Safe Singleton addresses (L2 version for most chains)
# Canonical deployment: 0x3E5c63644E683549055b9Be8653de26E0B4CD36E
# EIP-155 deployment: 0xfb1bffC9d739B8D520DaF37dF666da4C687191EA
# Both are functionally identical Safe L2 contracts, just deployed differently
SAFE_SINGLETON_L2_CANONICAL = "0x3E5c63644E683549055b9Be8653de26E0B4CD36E"
SAFE_SINGLETON_L2_EIP155 = "0xfb1bffC9d739B8D520DaF37dF666da4C687191EA"


@dataclass
class ChainConfig:
    """Configuration for a blockchain network."""

    chain_id: int
    name: str
    safe_tx_service_url: str
    rpc_url: str | None = None
    usdc_address: str | None = None
    allowance_module_address: str = "0xCFbFaC74C26F8647cBDb8c5caf80BB5b32E43134"
    # Safe singleton address - use L2 version for L2 chains
    safe_singleton_address: str = SAFE_SINGLETON_L2_EIP155


# Chain configurations mapping IntentKit network_id to Safe chain config
CHAIN_CONFIGS: dict[str, ChainConfig] = {
    # Mainnets
    "bnb-mainnet": ChainConfig(
        chain_id=56,
        name="BNB Smart Chain",
        safe_tx_service_url="https://safe-transaction-bsc.safe.global",
        usdc_address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        safe_singleton_address=SAFE_SINGLETON_L2_CANONICAL,
    ),
    "base-mainnet": ChainConfig(
        chain_id=8453,
        name="Base",
        safe_tx_service_url="https://safe-transaction-base.safe.global",
        usdc_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    ),
    "ethereum-mainnet": ChainConfig(
        chain_id=1,
        name="Ethereum",
        safe_tx_service_url="https://safe-transaction-mainnet.safe.global",
        usdc_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    ),
    "polygon-mainnet": ChainConfig(
        chain_id=137,
        name="Polygon",
        safe_tx_service_url="https://safe-transaction-polygon.safe.global",
        usdc_address="0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        # Note: Polygon uses different allowance module address
        allowance_module_address="0x1Fb403834C911eB98d56E74F5182b0d64C3b3b4D",
    ),
    "arbitrum-mainnet": ChainConfig(
        chain_id=42161,
        name="Arbitrum One",
        safe_tx_service_url="https://safe-transaction-arbitrum.safe.global",
        usdc_address="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    ),
    "optimism-mainnet": ChainConfig(
        chain_id=10,
        name="Optimism",
        safe_tx_service_url="https://safe-transaction-optimism.safe.global",
        usdc_address="0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
    ),
    # Testnets
    "base-sepolia": ChainConfig(
        chain_id=84532,
        name="Base Sepolia",
        safe_tx_service_url="https://safe-transaction-base-sepolia.safe.global",
        usdc_address="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        # Deployed custom Allowance Module v1.3.0 since canonical is missing
        allowance_module_address="0x3cfE2CEb10FC1654B5F4422704288D08BDF7d27F",
    ),
    "sepolia": ChainConfig(
        chain_id=11155111,
        name="Sepolia",
        safe_tx_service_url="https://safe-transaction-sepolia.safe.global",
        usdc_address="0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
    ),
}

# Safe contract addresses (same across most EVM chains for v1.3.0)
SAFE_PROXY_FACTORY_ADDRESS = "0xa6B71E26C5e0845f74c812102Ca7114b6a896AB2"
SAFE_FALLBACK_HANDLER_ADDRESS = "0xf48f2B2d2a534e402487b3ee7C18c33Aec0Fe5e4"
MULTI_SEND_ADDRESS = "0xA238CBeb142c10Ef7Ad8442C6D1f9E89e07e7761"
MULTI_SEND_CALL_ONLY_ADDRESS = "0x40A2aCCbd92BCA938b02010E17A5b8929b49130D"


# =============================================================================
# ABI Definitions
# =============================================================================

# Safe ABI (minimal for our needs)
SAFE_ABI = [
    {
        "inputs": [
            {"name": "_owners", "type": "address[]"},
            {"name": "_threshold", "type": "uint256"},
            {"name": "to", "type": "address"},
            {"name": "data", "type": "bytes"},
            {"name": "fallbackHandler", "type": "address"},
            {"name": "paymentToken", "type": "address"},
            {"name": "payment", "type": "uint256"},
            {"name": "paymentReceiver", "type": "address"},
        ],
        "name": "setup",
        "outputs": [],
        "type": "function",
    },
    {
        "inputs": [{"name": "module", "type": "address"}],
        "name": "enableModule",
        "outputs": [],
        "type": "function",
    },
    {
        "inputs": [{"name": "module", "type": "address"}],
        "name": "isModuleEnabled",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "inputs": [],
        "name": "nonce",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getOwners",
        "outputs": [{"name": "", "type": "address[]"}],
        "type": "function",
    },
]

# Allowance Module ABI
ALLOWANCE_MODULE_ABI = [
    {
        "inputs": [{"name": "delegate", "type": "address"}],
        "name": "addDelegate",
        "outputs": [],
        "type": "function",
    },
    {
        "inputs": [
            {"name": "delegate", "type": "address"},
            {"name": "token", "type": "address"},
            {"name": "allowanceAmount", "type": "uint96"},
            {"name": "resetTimeMin", "type": "uint16"},
            {"name": "resetBaseMin", "type": "uint32"},
        ],
        "name": "setAllowance",
        "outputs": [],
        "type": "function",
    },
    {
        "inputs": [
            {"name": "safe", "type": "address"},
            {"name": "delegate", "type": "address"},
            {"name": "token", "type": "address"},
        ],
        "name": "getTokenAllowance",
        "outputs": [{"name": "", "type": "uint256[5]"}],
        "type": "function",
    },
    {
        "inputs": [
            {"name": "safe", "type": "address"},
            {"name": "token", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint96"},
            {"name": "paymentToken", "type": "address"},
            {"name": "payment", "type": "uint96"},
            {"name": "nonce", "type": "uint16"},
        ],
        "name": "generateTransferHash",
        "outputs": [{"name": "", "type": "bytes32"}],
        "type": "function",
    },
    {
        "inputs": [
            {"name": "safe", "type": "address"},
            {"name": "token", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint96"},
            {"name": "paymentToken", "type": "address"},
            {"name": "payment", "type": "uint96"},
            {"name": "delegate", "type": "address"},
            {"name": "signature", "type": "bytes"},
        ],
        "name": "executeAllowanceTransfer",
        "outputs": [],
        "type": "function",
    },
]

# ERC20 ABI (minimal)
ERC20_ABI = [
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]


# SafeProxyFactory ABI
SAFE_PROXY_FACTORY_ABI = [
    {
        "inputs": [
            {"name": "_singleton", "type": "address"},
            {"name": "initializer", "type": "bytes"},
            {"name": "saltNonce", "type": "uint256"},
        ],
        "name": "createProxyWithNonce",
        "outputs": [{"name": "proxy", "type": "address"}],
        "type": "function",
    },
]


# =============================================================================
# Distributed Nonce Manager (Redis-based)
# =============================================================================

NONCE_LOCK_TTL = 30  # Lock expires after 30 seconds (prevents deadlocks)
NONCE_KEY_TTL = 3600  # Nonce cache expires after 1 hour


class MasterWalletNonceManager:
    """Distributed nonce manager using Redis for cross-process coordination.

    This prevents nonce collisions when multiple workers/container replicas
    use the same master wallet to pay for gas on Safe deployments.

    Uses Redis for:
    - nonce storage (shared across all processes)
    - distributed locking (SETNX pattern with TTL)
    """

    address: str
    _nonce_key: str
    _lock_key: str

    def __init__(self, address: str):
        self.address = to_checksum_address(address)
        self._nonce_key = f"intentkit:master_wallet:nonce:{address.lower()}"
        self._lock_key = f"intentkit:master_wallet:lock:{address.lower()}"

    async def acquire_lock(self, timeout: float = 10.0) -> bool:
        """Acquire distributed lock with timeout.

        Args:
            timeout: Maximum seconds to wait for lock acquisition

        Returns:
            True if lock acquired, False if timeout
        """
        import asyncio
        import time

        redis = get_redis()
        start = time.monotonic()

        while (time.monotonic() - start) < timeout:
            # SETNX pattern with TTL
            acquired = await redis.set(self._lock_key, "1", nx=True, ex=NONCE_LOCK_TTL)
            if acquired:
                return True
            await asyncio.sleep(0.05)  # Small delay before retry
        return False

    async def release_lock(self) -> None:
        """Release the distributed lock."""
        redis = get_redis()
        await redis.delete(self._lock_key)

    async def get_and_increment_nonce(self, w3: AsyncWeb3) -> int:
        """Get nonce from Redis (or blockchain if not cached) and atomically increment.

        Args:
            w3: AsyncWeb3 instance for blockchain queries

        Returns:
            The nonce to use for the current transaction
        """
        redis = get_redis()

        # Check if nonce is cached
        cached = await redis.get(self._nonce_key)
        if cached is None:
            # First time or expired - fetch from blockchain
            blockchain_nonce = await w3.eth.get_transaction_count(
                to_checksum_address(self.address)
            )
            # Set only if not exists (another worker might have set it)
            await redis.set(
                self._nonce_key, str(blockchain_nonce), nx=True, ex=NONCE_KEY_TTL
            )
            cached = await redis.get(self._nonce_key)

        current_nonce = int(str(cached))
        # Atomically increment for next caller
        await redis.incr(self._nonce_key)
        return current_nonce

    async def reset_from_blockchain(self, w3: AsyncWeb3) -> None:
        """Reset nonce cache from blockchain (call after tx failure).

        Args:
            w3: AsyncWeb3 instance for blockchain queries
        """
        redis = get_redis()
        blockchain_nonce = await w3.eth.get_transaction_count(
            to_checksum_address(self.address)
        )
        await redis.set(self._nonce_key, str(blockchain_nonce), ex=NONCE_KEY_TTL)
        logger.info(f"Reset master wallet nonce to {blockchain_nonce}")


# Module-level nonce manager instance (lazy init)
_nonce_manager: MasterWalletNonceManager | None = None


def _get_nonce_manager() -> MasterWalletNonceManager:
    """Get or create the nonce manager singleton for the master wallet."""
    global _nonce_manager
    if _nonce_manager is None:
        if not config.master_wallet_private_key:
            raise IntentKitAPIError(
                500, "ConfigError", "MASTER_WALLET_PRIVATE_KEY not configured"
            )
        master_account = Account.from_key(config.master_wallet_private_key)
        _nonce_manager = MasterWalletNonceManager(str(master_account.address))
    return _nonce_manager


# =============================================================================
# Data Models
# =============================================================================


class PrivyWallet(BaseModel):
    """Privy server wallet response model."""

    id: str
    address: str
    chain_type: str


@dataclass
class TransactionRequest:
    """A transaction request for the wallet provider."""

    to: str
    value: int = 0
    data: bytes = b""


@dataclass
class TransactionResult:
    """Result of a transaction execution."""

    success: bool
    tx_hash: str | None = None
    error: str | None = None


# =============================================================================
# Abstract Wallet Provider Interface
# =============================================================================


class WalletProvider(ABC):
    """
    Abstract base class for wallet providers.

    This interface allows different wallet implementations (Safe, CDP, etc.)
    to be used interchangeably by agents.
    """

    @abstractmethod
    async def get_address(self) -> str:
        """Get the wallet's public address."""
        pass

    @abstractmethod
    async def execute_transaction(
        self,
        to: str,
        value: int = 0,
        data: bytes = b"",
        chain_id: int | None = None,
    ) -> TransactionResult:
        """
        Execute a transaction.

        Args:
            to: Destination address
            value: Amount of native token to send (in wei)
            data: Transaction calldata
            chain_id: Optional chain ID (uses default if not specified)

        Returns:
            TransactionResult with success status and tx hash
        """
        pass

    @abstractmethod
    async def transfer_erc20(
        self,
        token_address: str,
        to: str,
        amount: int,
        chain_id: int | None = None,
    ) -> TransactionResult:
        """
        Transfer ERC20 tokens.

        Args:
            token_address: The token contract address
            to: Recipient address
            amount: Amount to transfer (in token's smallest unit)
            chain_id: Optional chain ID

        Returns:
            TransactionResult with success status and tx hash
        """
        pass

    @abstractmethod
    async def get_balance(self, chain_id: int | None = None) -> int:
        """Get native token balance in wei."""
        pass

    @abstractmethod
    async def get_erc20_balance(
        self,
        token_address: str,
        chain_id: int | None = None,
    ) -> int:
        """Get ERC20 token balance."""
        pass


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
                logger.error(f"Privy create key quorum failed: {response.text}")
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
                logger.error(f"Privy create wallet failed: {response.text}")
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
                logger.error(f"Privy get wallet failed: {response.text}")
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
                logger.error(f"Privy sign message failed: {response.text}")
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
                logger.error(f"Privy sign hash failed: {response.text}")
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
                logger.error(f"Privy sign typed data failed: {response.text}")
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
                logger.error(f"Privy send transaction failed: {response.text}")
                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    f"Failed to send transaction: {response.text}",
                )

            data_response = response.json()
            return data_response["data"]["hash"]


# =============================================================================
# Safe Smart Account Client
# =============================================================================


class SafeClient:
    """Client for interacting with Safe smart accounts."""

    def __init__(
        self,
        network_id: str = "base-mainnet",
        rpc_url: str | None = None,
    ) -> None:
        self.network_id = network_id
        self.chain_config = CHAIN_CONFIGS.get(network_id)
        if not self.chain_config:
            raise ValueError(f"Unsupported network: {network_id}")

        self.rpc_url = rpc_url or self.chain_config.rpc_url
        self.api_key: str | None = config.safe_api_key

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get_chain_id(self) -> int:
        """Get the chain ID for the current network."""
        if self.chain_config is None:
            raise ValueError("Chain config not initialized")
        return self.chain_config.chain_id

    def predict_safe_address(
        self,
        owner_address: str,
        salt_nonce: int = 0,
        threshold: int = 1,
    ) -> str:
        """
        Predict the counterfactual Safe address for a given owner.

        This calculates the CREATE2 address that would be deployed
        for a Safe with the given parameters.
        """
        owner_address = to_checksum_address(owner_address)

        # Build the initializer (setup call data)
        initializer = self._build_safe_initializer(
            owners=[owner_address],
            threshold=threshold,
        )

        # Calculate CREATE2 address
        return self._calculate_create2_address(initializer, salt_nonce)

    def _build_safe_initializer(
        self,
        owners: list[str],
        threshold: int,
        fallback_handler: str = SAFE_FALLBACK_HANDLER_ADDRESS,
    ) -> bytes:
        """Build the Safe setup initializer data."""
        # setup(address[] _owners, uint256 _threshold, address to, bytes data,
        #       address fallbackHandler, address paymentToken, uint256 payment, address paymentReceiver)
        setup_data = encode(
            [
                "address[]",
                "uint256",
                "address",
                "bytes",
                "address",
                "address",
                "uint256",
                "address",
            ],
            [
                owners,
                threshold,
                "0x0000000000000000000000000000000000000000",  # to
                b"",  # data
                fallback_handler,
                "0x0000000000000000000000000000000000000000",  # paymentToken
                0,  # payment
                "0x0000000000000000000000000000000000000000",  # paymentReceiver
            ],
        )

        # Function selector for setup()
        setup_selector = keccak(
            text="setup(address[],uint256,address,bytes,address,address,uint256,address)"
        )[:4]

        return setup_selector + setup_data

    def _calculate_create2_address(self, initializer: bytes, salt_nonce: int) -> str:
        """Calculate the CREATE2 address for a Safe deployment.

        The SafeProxyFactory calculates CREATE2 address as follows:
        - salt = keccak256(abi.encodePacked(keccak256(initializer), saltNonce))
        - deploymentData = abi.encodePacked(type(SafeProxy).creationCode, uint256(uint160(_singleton)))
        - address = keccak256(0xff ++ factory ++ salt ++ keccak256(deploymentData))[12:]

        Note: The initializer is NOT included in the deploymentData/init_code_hash,
        it's only used in the salt calculation.
        """
        # Salt = keccak256(keccak256(initializer) ++ saltNonce)
        initializer_hash = keccak(initializer)
        salt = keccak(initializer_hash + encode(["uint256"], [salt_nonce]))

        # Proxy creation code (Safe v1.3.0 GnosisSafeProxyFactory)
        # This is the bytecode that deploys a minimal proxy pointing to the singleton
        proxy_creation_code = bytes.fromhex(
            "608060405234801561001057600080fd5b506040516101e63803806101e68339818101604052602081101561003357600080fd5b8101908080519060200190929190505050600073ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff1614156100ca576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260228152602001806101c46022913960400191505060405180910390fd5b806000806101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055505060ab806101196000396000f3fe608060405273ffffffffffffffffffffffffffffffffffffffff600054167fa619486e0000000000000000000000000000000000000000000000000000000060003514156050578060005260206000f35b3660008037600080366000845af43d6000803e60008114156070573d6000fd5b3d6000f3fea2646970667358221220d1429297349653a4918076d650332de1a1068c5f3e07c5c82360c277770b955264736f6c63430007060033496e76616c69642073696e676c65746f6e20616464726573732070726f7669646564"
        )

        # deploymentData = creationCode + abi.encode(singleton)
        # Note: We do NOT include the initializer here - that's only for the salt
        # Use the chain-specific singleton address from ChainConfig
        if self.chain_config is None:
            raise ValueError("Chain config not initialized")
        singleton_address = self.chain_config.safe_singleton_address
        init_code = proxy_creation_code + encode(["address"], [singleton_address])
        init_code_hash = keccak(init_code)

        # CREATE2 address calculation: keccak256(0xff ++ factory ++ salt ++ init_code_hash)[12:]
        factory_address = bytes.fromhex(SAFE_PROXY_FACTORY_ADDRESS[2:])
        create2_input = b"\xff" + factory_address + salt + init_code_hash
        address_bytes = keccak(create2_input)[12:]

        return to_checksum_address(address_bytes)

    async def is_deployed(self, address: str, rpc_url: str) -> bool:
        """Check if a contract is deployed at the given address."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getCode",
                    "params": [address, "latest"],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                return False

            result = response.json().get("result", "0x")
            return len(result) > 2

    async def get_safe_info(self, safe_address: str) -> dict[str, Any] | None:
        """Get Safe information from the Transaction Service."""
        if self.chain_config is None:
            raise ValueError("Chain config not initialized")
        url = f"{self.chain_config.safe_tx_service_url}/api/v1/safes/{safe_address}/"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), timeout=30.0)

            if response.status_code == 404:
                return None
            elif response.status_code != 200:
                logger.error(f"Safe get info failed: {response.text}")
                return None

            return response.json()

    async def get_nonce(self, safe_address: str, rpc_url: str) -> int:
        """Get the current nonce for a Safe."""
        # Encode the nonce() call
        nonce_selector = keccak(text="nonce()")[:4]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {"to": safe_address, "data": "0x" + nonce_selector.hex()},
                        "latest",
                    ],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise IntentKitAPIError(500, "RPCError", "Failed to get Safe nonce")

            result = response.json().get("result", "0x0")
            return int(result, 16)


# =============================================================================
# Safe Wallet Provider (implements WalletProvider interface)
# =============================================================================


class SafeWalletProvider(WalletProvider):
    """
    Safe smart account wallet provider.

    This provider uses a Privy EOA as the owner/signer and a Safe smart
    account as the public address with spending limit support.
    """

    def __init__(
        self,
        privy_wallet_id: str,
        privy_wallet_address: str,
        safe_address: str,
        network_id: str = "base-mainnet",
        rpc_url: str | None = None,
    ) -> None:
        self.privy_wallet_id = privy_wallet_id
        self.privy_wallet_address = to_checksum_address(privy_wallet_address)
        self.safe_address = to_checksum_address(safe_address)
        self.network_id = network_id

        self.chain_config = CHAIN_CONFIGS.get(network_id)
        if not self.chain_config:
            raise ValueError(f"Unsupported network: {network_id}")

        self.rpc_url = rpc_url
        self.privy_client = PrivyClient()
        self.safe_client = SafeClient(network_id, rpc_url)

    async def get_address(self) -> str:
        """Get the Safe smart account address."""
        return self.safe_address

    async def execute_transaction(
        self,
        to: str,
        value: int = 0,
        data: bytes = b"",
        chain_id: int | None = None,
    ) -> TransactionResult:
        """
        Execute a transaction through the Safe.

        For now, this uses the Privy EOA to directly execute transactions
        on behalf of the Safe (as owner). In the future, this could use
        the Safe Transaction Service for better UX.
        """
        try:
            # Get the RPC URL for the chain
            if self.chain_config is None:
                return TransactionResult(
                    success=False,
                    error="Chain config not initialized",
                )
            target_chain_id = chain_id or self.chain_config.chain_id
            rpc_url = self._get_rpc_url_for_chain(target_chain_id)

            if not rpc_url:
                return TransactionResult(
                    success=False,
                    error=f"No RPC URL configured for chain {target_chain_id}",
                )

            # Build Safe transaction
            safe_tx_data = self._encode_safe_exec_transaction(to, value, data)

            # Send via Privy
            tx_hash = await self.privy_client.send_transaction(
                wallet_id=self.privy_wallet_id,
                chain_id=target_chain_id,
                to=self.safe_address,
                value=0,
                data="0x" + safe_tx_data.hex(),
            )

            return TransactionResult(success=True, tx_hash=tx_hash)

        except Exception as e:
            logger.error(f"Transaction execution failed: {e}")
            return TransactionResult(success=False, error=str(e))

    async def transfer_erc20(
        self,
        token_address: str,
        to: str,
        amount: int,
        chain_id: int | None = None,
        force_admin_execution: bool = False,
    ) -> TransactionResult:
        """Transfer ERC20 tokens from the Safe.

        Uses Allowance Module if enabled to enforce spending limits.
        Falls back to direct owner execution if not enabled.

        Args:
            force_admin_execution: If True, bypass allowance module and use direct owner transfer
                                 even if the module is enabled.
        """
        if self.chain_config is None:
            return TransactionResult(
                success=False,
                error="Chain config not initialized",
            )
        target_chain_id = chain_id or self.chain_config.chain_id
        rpc_url = self._get_rpc_url_for_chain(target_chain_id)
        if not rpc_url:
            return TransactionResult(
                success=False,
                error=f"No RPC URL configured for chain {target_chain_id}",
            )

        # Check if Allowance Module is enabled
        allowance_module = self.chain_config.allowance_module_address
        is_enabled = await _is_module_enabled(
            rpc_url=rpc_url,
            safe_address=self.safe_address,
            module_address=allowance_module,
        )

        if is_enabled and not force_admin_execution:
            logger.info("Allowance Module enabled, using allowance transfer")
            return await self.execute_allowance_transfer(
                token_address=token_address,
                to=to,
                amount=amount,
                chain_id=chain_id,
            )

        if is_enabled and force_admin_execution:
            logger.info(
                "Allowance Module enabled but force_admin_execution is True, bypassing allowance"
            )

        logger.info("Using direct owner transfer (Allowance disabled or forced admin)")
        # Encode ERC20 transfer call
        transfer_selector = keccak(text="transfer(address,uint256)")[:4]
        transfer_data = transfer_selector + encode(
            ["address", "uint256"],
            [to_checksum_address(to), amount],
        )

        return await self.execute_transaction(
            to=to_checksum_address(token_address),
            value=0,
            data=transfer_data,
            chain_id=chain_id,
        )

    async def execute_allowance_transfer(
        self,
        token_address: str,
        to: str,
        amount: int,
        chain_id: int | None = None,
    ) -> TransactionResult:
        """
        Execute a token transfer using the Allowance Module.

        This allows the agent (as delegate) to spend tokens within
        the configured spending limit without requiring owner signatures.
        """
        try:
            if self.chain_config is None:
                return TransactionResult(
                    success=False,
                    error="Chain config not initialized",
                )
            target_chain_id = chain_id or self.chain_config.chain_id
            rpc_url = self._get_rpc_url_for_chain(target_chain_id)

            if not rpc_url:
                return TransactionResult(
                    success=False,
                    error=f"No RPC URL configured for chain {target_chain_id}",
                )

            # Get allowance module address for this chain
            chain_config = self._get_chain_config_for_id(target_chain_id)
            if not chain_config:
                return TransactionResult(
                    success=False,
                    error=f"Chain {target_chain_id} not configured",
                )

            allowance_module = chain_config.allowance_module_address

            # Get current allowance nonce
            nonce = await self._get_allowance_nonce(
                rpc_url, allowance_module, token_address
            )

            # Generate transfer hash
            transfer_hash = await self._generate_transfer_hash(
                rpc_url=rpc_url,
                allowance_module=allowance_module,
                token_address=token_address,
                to=to,
                amount=amount,
                nonce=nonce,
            )

            # Sign the hash with Privy
            signature = await self.privy_client.sign_hash(
                self.privy_wallet_id, transfer_hash
            )

            # Execute the allowance transfer
            exec_data = self._encode_execute_allowance_transfer(
                token_address=token_address,
                to=to,
                amount=amount,
                signature=signature,
            )

            # Send the transaction (anyone can submit this with valid signature)
            tx_hash = await self.privy_client.send_transaction(
                wallet_id=self.privy_wallet_id,
                chain_id=target_chain_id,
                to=allowance_module,
                value=0,
                data="0x" + exec_data.hex(),
            )

            return TransactionResult(success=True, tx_hash=tx_hash)

        except Exception as e:
            logger.error(f"Allowance transfer failed: {e}")
            return TransactionResult(success=False, error=str(e))

    async def get_balance(self, chain_id: int | None = None) -> int:
        """Get native token balance of the Safe."""
        if self.chain_config is None:
            raise ValueError("Chain config not initialized")
        target_chain_id = chain_id or self.chain_config.chain_id
        rpc_url = self._get_rpc_url_for_chain(target_chain_id)

        if not rpc_url:
            raise IntentKitAPIError(
                500, "ConfigError", f"No RPC URL for chain {target_chain_id}"
            )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getBalance",
                    "params": [self.safe_address, "latest"],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise IntentKitAPIError(500, "RPCError", "Failed to get balance")

            result = response.json().get("result", "0x0")
            return int(result, 16)

    async def get_erc20_balance(
        self,
        token_address: str,
        chain_id: int | None = None,
    ) -> int:
        """Get ERC20 token balance of the Safe."""
        if self.chain_config is None:
            raise ValueError("Chain config not initialized")
        target_chain_id = chain_id or self.chain_config.chain_id
        rpc_url = self._get_rpc_url_for_chain(target_chain_id)

        if not rpc_url:
            raise IntentKitAPIError(
                500, "ConfigError", f"No RPC URL for chain {target_chain_id}"
            )

        # Encode balanceOf call
        balance_selector = keccak(text="balanceOf(address)")[:4]
        call_data = balance_selector + encode(["address"], [self.safe_address])

        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {
                            "to": to_checksum_address(token_address),
                            "data": "0x" + call_data.hex(),
                        },
                        "latest",
                    ],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise IntentKitAPIError(500, "RPCError", "Failed to get token balance")

            result = response.json().get("result", "0x0")
            return int(result, 16)

    def _get_rpc_url_for_chain(self, chain_id: int) -> str | None:
        """Get RPC URL for a specific chain ID."""
        if self.chain_config is None:
            return None
        if self.rpc_url and self.chain_config.chain_id == chain_id:
            return self.rpc_url

        for chain_cfg in CHAIN_CONFIGS.values():
            if chain_cfg.chain_id == chain_id:
                return chain_cfg.rpc_url

        return None

    def _get_chain_config_for_id(self, chain_id: int) -> ChainConfig | None:
        """Get chain config for a specific chain ID."""
        for chain_cfg in CHAIN_CONFIGS.values():
            if chain_cfg.chain_id == chain_id:
                return chain_cfg
        return None

    def _encode_safe_exec_transaction(
        self,
        to: str,
        value: int,
        data: bytes,
        signature: bytes | None = None,
    ) -> bytes:
        """Encode a Safe execTransaction call.

        Args:
            to: Target address
            value: ETH value to send
            data: Call data
            signature: Optional ECDSA signature. If not provided, uses pre-validated
                       signature format (requires msg.sender == owner).
        """
        # execTransaction(address to, uint256 value, bytes data, uint8 operation,
        #                 uint256 safeTxGas, uint256 baseGas, uint256 gasPrice,
        #                 address gasToken, address refundReceiver, bytes signatures)
        exec_selector = keccak(
            text="execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)"
        )[:4]

        if signature is not None:
            # Use the provided ECDSA signature
            signatures = signature
        else:
            # For owner execution, we use a pre-validated signature
            # This is the signature format for msg.sender == owner
            signatures = bytes.fromhex(
                self.privy_wallet_address[2:].lower().zfill(64)  # r = owner address
                + "0" * 64  # s = 0
                + "01"  # v = 1 (indicates approved hash)
            )

        exec_data = encode(
            [
                "address",
                "uint256",
                "bytes",
                "uint8",
                "uint256",
                "uint256",
                "uint256",
                "address",
                "address",
                "bytes",
            ],
            [
                to_checksum_address(to),
                value,
                data,
                0,  # operation (0 = Call)
                0,  # safeTxGas
                0,  # baseGas
                0,  # gasPrice
                "0x0000000000000000000000000000000000000000",  # gasToken
                "0x0000000000000000000000000000000000000000",  # refundReceiver
                signatures,
            ],
        )

        return exec_selector + exec_data

    async def _get_allowance_nonce(
        self,
        rpc_url: str,
        allowance_module: str,
        token_address: str,
    ) -> int:
        """Get the current nonce for an allowance."""
        # getTokenAllowance(address safe, address delegate, address token)
        selector = keccak(text="getTokenAllowance(address,address,address)")[:4]
        call_data = selector + encode(
            ["address", "address", "address"],
            [self.safe_address, self.privy_wallet_address, token_address],
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {"to": allowance_module, "data": "0x" + call_data.hex()},
                        "latest",
                    ],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise IntentKitAPIError(500, "RPCError", "Failed to get allowance")

            result = response.json().get("result", "0x")
            # Result is uint256[5]: [amount, spent, resetTimeMin, lastResetMin, nonce]
            if len(result) >= 322:  # 2 + 5 * 64
                nonce_hex = result[258:322]  # 5th element
                return int(nonce_hex, 16)
            return 0

    async def _generate_transfer_hash(
        self,
        rpc_url: str,
        allowance_module: str,
        token_address: str,
        to: str,
        amount: int,
        nonce: int,
    ) -> bytes:
        """Generate the hash for an allowance transfer."""
        # generateTransferHash(address safe, address token, address to, uint96 amount,
        #                      address paymentToken, uint96 payment, uint16 nonce)
        selector = keccak(
            text="generateTransferHash(address,address,address,uint96,address,uint96,uint16)"
        )[:4]
        call_data = selector + encode(
            ["address", "address", "address", "uint96", "address", "uint96", "uint16"],
            [
                self.safe_address,
                to_checksum_address(token_address),
                to_checksum_address(to),
                amount,
                "0x0000000000000000000000000000000000000000",  # paymentToken
                0,  # payment
                nonce,
            ],
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {"to": allowance_module, "data": "0x" + call_data.hex()},
                        "latest",
                    ],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise IntentKitAPIError(500, "RPCError", "Failed to generate hash")

            result = response.json().get("result", "0x")
            return bytes.fromhex(result[2:])

    def _encode_execute_allowance_transfer(
        self,
        token_address: str,
        to: str,
        amount: int,
        signature: str,
    ) -> bytes:
        """Encode executeAllowanceTransfer call."""
        # executeAllowanceTransfer(address safe, address token, address to, uint96 amount,
        #                          address paymentToken, uint96 payment, address delegate, bytes signature)
        selector = keccak(
            text="executeAllowanceTransfer(address,address,address,uint96,address,uint96,address,bytes)"
        )[:4]

        sig_bytes = bytes.fromhex(
            signature[2:] if signature.startswith("0x") else signature
        )

        exec_data = encode(
            [
                "address",
                "address",
                "address",
                "uint96",
                "address",
                "uint96",
                "address",
                "bytes",
            ],
            [
                self.safe_address,
                to_checksum_address(token_address),
                to_checksum_address(to),
                amount,
                "0x0000000000000000000000000000000000000000",  # paymentToken
                0,  # payment
                self.privy_wallet_address,  # delegate
                sig_bytes,
            ],
        )

        return selector + exec_data


# =============================================================================
# Safe Deployment and Setup Functions
# =============================================================================


async def deploy_safe_with_allowance(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    privy_wallet_address: str,
    network_id: str,
    rpc_url: str,
    weekly_spending_limit_usdc: float | None = None,
) -> dict[str, Any]:
    """
    Deploy a Safe smart account and configure the Allowance Module.

    This function:
    1. Deploys a new Safe with the Privy wallet as owner
    2. Enables the Allowance Module
    3. Adds the Privy wallet as a delegate
    4. Sets up weekly USDC spending limit if specified

    Args:
        privy_client: Initialized Privy client
        privy_wallet_id: Privy wallet ID
        privy_wallet_address: Privy wallet EOA address
        network_id: Network identifier (e.g., "base-mainnet")
        rpc_url: RPC URL for the network
        weekly_spending_limit_usdc: Weekly USDC spending limit (optional)

    Returns:
        dict with deployment info including safe_address and tx_hashes
    """
    chain_config = CHAIN_CONFIGS.get(network_id)
    if not chain_config:
        raise ValueError(f"Unsupported network: {network_id}")

    safe_client = SafeClient(network_id, rpc_url)
    owner_address = to_checksum_address(privy_wallet_address)

    # Calculate salt nonce from wallet address for determinism
    salt_nonce = int.from_bytes(keccak(text=privy_wallet_id)[:8], "big")

    # Predict the Safe address
    predicted_address = safe_client.predict_safe_address(
        owner_address=owner_address,
        salt_nonce=salt_nonce,
        threshold=1,
    )

    result: dict[str, Any] = {
        "safe_address": predicted_address,
        "owner_address": owner_address,
        "network_id": network_id,
        "chain_id": chain_config.chain_id,
        "salt_nonce": salt_nonce,
        "tx_hashes": [],
        "allowance_module_enabled": False,
        "spending_limit_configured": False,
    }

    # Check if already deployed
    is_deployed = await safe_client.is_deployed(predicted_address, rpc_url)
    if is_deployed:
        logger.info(f"Safe already deployed at {predicted_address}")
        result["already_deployed"] = True
    else:
        # Deploy the Safe
        logger.info(f"Deploying Safe to {predicted_address}")
        deploy_tx_hash, actual_address = await _deploy_safe(
            owner_address=owner_address,
            salt_nonce=salt_nonce,
            chain_id=chain_config.chain_id,
            rpc_url=rpc_url,
            singleton_address=chain_config.safe_singleton_address,
        )
        result["tx_hashes"].append({"deploy_safe": deploy_tx_hash})
        result["already_deployed"] = False

        # Validate that predicted address matches actual deployed address
        if actual_address.lower() != predicted_address.lower():
            raise IntentKitAPIError(
                500,
                "AddressMismatch",
                f"Safe address prediction mismatch: predicted {predicted_address}, "
                f"but actually deployed to {actual_address}. "
                "This indicates a bug in the CREATE2 address calculation.",
            )
        logger.info(f"Safe address validated: {predicted_address}")

        # Wait for Safe to be visible across RPC nodes before proceeding
        # This prevents race conditions where subsequent operations fail because
        # the RPC node hasn't synced the new contract yet
        safe_visible = await _wait_for_safe_deployed(
            safe_address=predicted_address,
            rpc_url=rpc_url,
            max_retries=15,  # Up to 15 seconds of waiting
            retry_delay=1.0,
        )
        if not safe_visible:
            raise IntentKitAPIError(
                500,
                "DeploymentSyncTimeout",
                f"Safe {predicted_address} deployed but not visible after waiting. "
                "RPC node may be slow to sync. Please retry.",
            )

    # If we just deployed, we know the nonce is 0.
    # Otherwise, we fetch it initially.
    # We will track it locally to avoid race conditions with RPC nodes that lag behind.
    current_nonce = 0
    if result["already_deployed"]:
        current_nonce = await _get_safe_nonce(predicted_address, rpc_url)

    if weekly_spending_limit_usdc is not None:
        module_enabled = await _is_module_enabled(
            rpc_url=rpc_url,
            safe_address=predicted_address,
            module_address=chain_config.allowance_module_address,
        )
        result["allowance_module_enabled"] = module_enabled

        if weekly_spending_limit_usdc > 0 and not module_enabled:
            logger.info("Enabling Allowance Module")
            enable_tx_hash = await _enable_allowance_module(
                privy_client=privy_client,
                privy_wallet_id=privy_wallet_id,
                safe_address=predicted_address,
                owner_address=owner_address,
                allowance_module_address=chain_config.allowance_module_address,
                chain_id=chain_config.chain_id,
                rpc_url=rpc_url,
                nonce=current_nonce,
            )
            result["tx_hashes"].append({"enable_module": enable_tx_hash})
            result["allowance_module_enabled"] = True
            current_nonce += 1

        if chain_config.usdc_address and (
            weekly_spending_limit_usdc > 0 or module_enabled
        ):
            logger.info(
                f"Setting weekly spending limit: {weekly_spending_limit_usdc} USDC"
            )
            limit_tx_hash = await _set_spending_limit(
                privy_client=privy_client,
                privy_wallet_id=privy_wallet_id,
                safe_address=predicted_address,
                owner_address=owner_address,
                delegate_address=owner_address,
                token_address=chain_config.usdc_address,
                allowance_amount=int(weekly_spending_limit_usdc * 1_000_000),
                reset_time_minutes=7 * 24 * 60,
                allowance_module_address=chain_config.allowance_module_address,
                chain_id=chain_config.chain_id,
                rpc_url=rpc_url,
                nonce=current_nonce,
            )
            result["tx_hashes"].append({"set_spending_limit": limit_tx_hash})
            result["spending_limit_configured"] = True
            current_nonce += 1

    return result


async def _deploy_safe(
    owner_address: str,
    salt_nonce: int,
    chain_id: int,
    rpc_url: str,
    singleton_address: str,
) -> tuple[str, str]:
    """Deploy a new Safe via the ProxyFactory using master wallet.

    The master wallet pays for gas, but the Safe is owned by owner_address.
    This allows creating Safes for Privy wallets without them needing gas.

    Args:
        owner_address: The address that will own the Safe (Privy wallet address)
        salt_nonce: Salt for deterministic address generation
        chain_id: The chain ID to deploy on
        rpc_url: RPC URL for the chain
        singleton_address: The Safe singleton (implementation) address to use

    Returns:
        Tuple of (transaction_hash, deployed_safe_address)
    """
    if not config.master_wallet_private_key:
        raise IntentKitAPIError(
            500,
            "ConfigError",
            "MASTER_WALLET_PRIVATE_KEY not configured. "
            "A master wallet is required to pay for Safe deployments.",
        )

    # Build initializer
    safe_client = SafeClient()
    initializer = safe_client._build_safe_initializer(
        owners=[owner_address],
        threshold=1,
    )

    # Encode createProxyWithNonce call
    create_selector = keccak(text="createProxyWithNonce(address,bytes,uint256)")[:4]
    create_data = create_selector + encode(
        ["address", "bytes", "uint256"],
        [singleton_address, initializer, salt_nonce],
    )

    # Use master wallet to send transaction
    w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
    master_account = Account.from_key(config.master_wallet_private_key)

    logger.info(
        f"Deploying Safe for owner {owner_address} using master wallet {master_account.address}"
    )

    # Use distributed nonce manager with lock
    nonce_manager = _get_nonce_manager()
    if not await nonce_manager.acquire_lock():
        raise IntentKitAPIError(
            500, "LockTimeout", "Failed to acquire nonce lock for Safe deployment"
        )

    try:
        # Get nonce from Redis (or blockchain if not cached)
        nonce = await nonce_manager.get_and_increment_nonce(w3)
        gas_price = await w3.eth.gas_price

        tx: dict[str, Any] = {
            "from": master_account.address,
            "to": SAFE_PROXY_FACTORY_ADDRESS,
            "value": 0,
            "data": create_data,
            "nonce": nonce,
            "chainId": chain_id,
            "gas": 500000,  # Safe deployment typically needs ~300k gas
            "gasPrice": gas_price,
        }

        # Estimate gas
        try:
            estimated_gas = await w3.eth.estimate_gas(cast(TxParams, cast(object, tx)))
            tx["gas"] = int(estimated_gas * 1.2)  # Add 20% buffer
            logger.debug(f"Estimated gas for Safe deployment: {estimated_gas}")
        except Exception as e:
            logger.warning(f"Gas estimation failed, using default 500000: {e}")

        # Sign and send
        signed_tx = master_account.sign_transaction(tx)
        tx_hash = await w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info(f"Safe deployment tx sent: {tx_hash.hex()}")

    except Exception as e:
        # Reset nonce on error (might be nonce-related)
        error_msg = str(e).lower()
        if "nonce" in error_msg:
            logger.warning(f"Nonce error detected, resetting from blockchain: {e}")
            await nonce_manager.reset_from_blockchain(w3)
        raise
    finally:
        await nonce_manager.release_lock()

    # Wait for confirmation
    receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt["status"] != 1:
        raise IntentKitAPIError(
            500, "DeploymentFailed", "Safe deployment transaction failed"
        )

    # Extract the deployed Safe address from ProxyCreation event
    # Event signature: ProxyCreation(address proxy, address singleton)
    # Topic: keccak256("ProxyCreation(address,address)")
    proxy_creation_topic = keccak(text="ProxyCreation(address,address)").hex()
    actual_safe_address: str | None = None

    for log in receipt.get("logs", []):
        topics = log.get("topics", [])
        if topics and topics[0].hex() == proxy_creation_topic:
            # The proxy address is in the event data (first 32 bytes, padded)
            raw_data = log.get("data", b"")
            if isinstance(raw_data, (bytes, bytearray, memoryview)):
                log_data_bytes = bytes(raw_data)
            else:
                raw_str = str(raw_data)
                hex_str = raw_str[2:] if raw_str.startswith("0x") else raw_str
                log_data_bytes = bytes.fromhex(hex_str)
            if len(log_data_bytes) >= 32:
                # Extract address from first 32 bytes (last 20 bytes are the address)
                actual_safe_address = to_checksum_address(log_data_bytes[12:32])
                break

    if not actual_safe_address:
        raise IntentKitAPIError(
            500,
            "DeploymentFailed",
            "Could not extract deployed Safe address from ProxyCreation event",
        )

    logger.info(
        f"Safe deployed successfully. Tx hash: {tx_hash.hex()}, "
        f"Gas used: {receipt['gasUsed']}, Address: {actual_safe_address}"
    )

    return tx_hash.hex(), actual_safe_address


async def _is_module_enabled(
    rpc_url: str,
    safe_address: str,
    module_address: str,
) -> bool:
    """Check if a module is enabled on a Safe."""
    # isModuleEnabled(address module)
    selector = keccak(text="isModuleEnabled(address)")[:4]
    call_data = selector + encode(["address"], [module_address])

    async with httpx.AsyncClient() as client:
        response = await client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {"to": safe_address, "data": "0x" + call_data.hex()},
                    "latest",
                ],
                "id": 1,
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            return False

        result = response.json().get("result", "0x")
        return result.endswith("1")


async def _wait_for_safe_deployed(
    safe_address: str,
    rpc_url: str,
    max_retries: int = 10,
    retry_delay: float = 1.0,
) -> bool:
    """Wait for Safe contract to be visible on the RPC node.

    After deploying a Safe, there can be a delay before the contract code
    is visible across all RPC nodes (especially with load-balanced endpoints).
    This function polls eth_getCode to confirm the Safe is deployed before
    proceeding with subsequent operations like enabling modules.

    Args:
        safe_address: The Safe contract address
        rpc_url: RPC URL for the network
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        True if Safe is deployed and visible, False if max retries exceeded
    """
    import asyncio

    for attempt in range(max_retries):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getCode",
                    "params": [safe_address, "latest"],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code == 200:
                result = response.json().get("result", "0x")
                if len(result) > 2:  # Has contract code
                    if attempt > 0:
                        logger.info(
                            f"Safe {safe_address} visible after {attempt + 1} attempts"
                        )
                    return True

        if attempt < max_retries - 1:
            logger.debug(
                f"Safe {safe_address} not yet visible, retry {attempt + 1}/{max_retries}"
            )
            await asyncio.sleep(retry_delay)

    logger.warning(f"Safe {safe_address} not visible after {max_retries} attempts")
    return False


def _get_safe_tx_hash(
    safe_address: str,
    to: str,
    value: int,
    data: bytes,
    nonce: int,
    chain_id: int,
    operation: int = 0,
) -> bytes:
    """Calculate the Safe transaction hash for signing.

    This generates the EIP-712 typed data hash that owners must sign.

    Args:
        safe_address: The Safe contract address
        to: Target address for the transaction
        value: ETH value in wei
        data: Transaction calldata
        nonce: Safe nonce
        chain_id: Chain ID
        operation: 0 for Call, 1 for DelegateCall (default: 0)

    Returns:
        The EIP-712 hash to sign
    """
    # Domain separator
    domain_type_hash = keccak(
        text="EIP712Domain(uint256 chainId,address verifyingContract)"
    )
    domain_separator = keccak(
        domain_type_hash
        + encode(["uint256", "address"], [chain_id, to_checksum_address(safe_address)])
    )

    # Safe tx type hash
    safe_tx_type_hash = keccak(
        text="SafeTx(address to,uint256 value,bytes data,uint8 operation,uint256 safeTxGas,uint256 baseGas,uint256 gasPrice,address gasToken,address refundReceiver,uint256 nonce)"
    )

    # Encode the transaction data
    data_hash = keccak(data)
    safe_tx_hash_data = encode(
        [
            "bytes32",
            "address",
            "uint256",
            "bytes32",
            "uint8",
            "uint256",
            "uint256",
            "uint256",
            "address",
            "address",
            "uint256",
        ],
        [
            safe_tx_type_hash,
            to_checksum_address(to),
            value,
            data_hash,
            operation,  # operation: 0 = Call, 1 = DelegateCall
            0,  # safeTxGas
            0,  # baseGas
            0,  # gasPrice
            "0x0000000000000000000000000000000000000000",  # gasToken
            "0x0000000000000000000000000000000000000000",  # refundReceiver
            nonce,
        ],
    )
    struct_hash = keccak(safe_tx_hash_data)

    # Final hash: keccak256("\x19\x01" + domainSeparator + structHash)
    return keccak(b"\x19\x01" + domain_separator + struct_hash)


async def _get_safe_nonce(safe_address: str, rpc_url: str) -> int:
    """Get the current nonce of a Safe."""
    selector = keccak(text="nonce()")[:4]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {"to": safe_address, "data": "0x" + selector.hex()},
                    "latest",
                ],
                "id": 1,
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            raise IntentKitAPIError(500, "RPCError", "Failed to get Safe nonce")

        result = response.json().get("result", "0x0")
        # Handle empty result '0x' as 0
        if result == "0x" or not result:
            return 0
        return int(result, 16)


async def _send_transaction_with_master_wallet(
    to: str,
    data: bytes,
    chain_id: int,
    rpc_url: str,
    gas_limit: int = 300000,
) -> str:
    """Send a transaction using master wallet to pay for gas.

    Args:
        to: Target address
        data: Transaction data
        chain_id: Chain ID
        rpc_url: RPC URL
        gas_limit: Gas limit (default: 300000)

    Returns:
        Transaction hash
    """
    if not config.master_wallet_private_key:
        raise IntentKitAPIError(
            500,
            "ConfigError",
            "MASTER_WALLET_PRIVATE_KEY not configured",
        )

    w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
    master_account = Account.from_key(config.master_wallet_private_key)

    # Use distributed nonce manager with lock
    nonce_manager = _get_nonce_manager()
    if not await nonce_manager.acquire_lock():
        raise IntentKitAPIError(
            500, "LockTimeout", "Failed to acquire nonce lock for transaction"
        )

    try:
        # Get nonce from Redis (or blockchain if not cached)
        nonce = await nonce_manager.get_and_increment_nonce(w3)
        gas_price = await w3.eth.gas_price

        tx: dict[str, Any] = {
            "from": master_account.address,
            "to": to,
            "value": 0,
            "data": data,
            "nonce": nonce,
            "chainId": chain_id,
            "gas": gas_limit,
            "gasPrice": gas_price,
        }

        try:
            estimated_gas = await w3.eth.estimate_gas(cast(TxParams, cast(object, tx)))
            # Add 20% buffer, but don't exceed block gas limit blindly
            tx["gas"] = int(estimated_gas * 1.2)
        except Exception as e:
            logger.warning(f"Gas estimation failed, using default {gas_limit}: {e}")

        signed_tx = master_account.sign_transaction(tx)
        tx_hash = await w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info(f"Transaction sent via master wallet: {tx_hash.hex()}")

    except Exception as e:
        # Reset nonce on error (might be nonce-related)
        error_msg = str(e).lower()
        if "nonce" in error_msg:
            logger.warning(f"Nonce error detected, resetting from blockchain: {e}")
            await nonce_manager.reset_from_blockchain(w3)
        raise
    finally:
        await nonce_manager.release_lock()

    receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt["status"] != 1:
        # Check for revert reason if possible
        # This is where we could try to decode the error, but for now just fail
        logger.error(f"Transaction {tx_hash.hex()} failed/reverted")
        raise IntentKitAPIError(500, "TxFailed", "Transaction failed on-chain")

    return tx_hash.hex()


async def _send_safe_transaction_with_master_wallet(
    safe_address: str,
    exec_data: bytes,
    chain_id: int,
    rpc_url: str,
) -> str:
    """Send a Safe transaction using master wallet to pay for gas.

    This function sends a pre-encoded Safe execTransaction call using the
    master wallet to pay for gas. The transaction must already be properly
    signed by the Safe owner.

    Args:
        safe_address: The Safe contract address
        exec_data: Encoded execTransaction call data (including signatures)
        chain_id: Chain ID
        rpc_url: RPC URL

    Returns:
        Transaction hash
    """
    # Send the transaction via master wallet
    # execTransaction can be gas hungry, so we keep the default 300k
    # (actually Safe transactions often need more depending on logic,
    # but the generic sender estimates gas which corrects this)
    tx_hash_hex = await _send_transaction_with_master_wallet(
        to=safe_address,
        data=exec_data,
        chain_id=chain_id,
        rpc_url=rpc_url,
        gas_limit=500000,  # Safe txs can be heavy
    )

    # Verify Safe execution succeeded by checking for ExecutionSuccess event
    # Safe's execTransaction returns false (doesn't revert) on internal failure,
    # so we must check the logs for ExecutionSuccess/ExecutionFailure events.
    w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
    receipt = await w3.eth.get_transaction_receipt(HexBytes(tx_hash_hex))

    # Event signatures:
    # - ExecutionSuccess(bytes32,uint256): 0x442e715f...
    # - ExecutionFailure(bytes32,uint256): 0x23428b18...
    execution_success_topic = (
        "0x442e715f626346e8c54381002da614f62bee8d27386535b2521ec8540898556e"
    )
    execution_failure_topic = (
        "0x23428b18acfb3ea64b08dc0c1d296ea9c09702c09083ca5272e64d115b687d23"
    )

    execution_success = False
    execution_failed = False

    for log in receipt.get("logs", []):
        topics = log.get("topics", [])
        if topics:
            topic_hex = topics[0].hex() if hasattr(topics[0], "hex") else str(topics[0])
            # Normalize topic (add 0x prefix if missing)
            if not topic_hex.startswith("0x"):
                topic_hex = "0x" + topic_hex

            if topic_hex == execution_success_topic:
                execution_success = True
                break
            elif topic_hex == execution_failure_topic:
                execution_failed = True
                break

    if execution_failed:
        raise IntentKitAPIError(
            500,
            "SafeExecutionFailed",
            "Safe execTransaction returned failure. "
            "This typically means the signature is invalid or the signer is not a Safe owner.",
        )

    if not execution_success:
        # No ExecutionSuccess event found - the Safe execution likely failed silently
        # This can happen if the signature verification fails before execTransaction runs
        logger.warning(
            f"No ExecutionSuccess event found in Safe transaction {tx_hash_hex}. "
            f"Logs: {receipt.get('logs', [])}"
        )
        raise IntentKitAPIError(
            500,
            "SafeExecutionFailed",
            "Safe transaction completed but no ExecutionSuccess event was found. "
            "The Safe execution may have failed. Please verify the signer is a Safe owner.",
        )

    return tx_hash_hex


async def _enable_allowance_module(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    safe_address: str,
    owner_address: str,
    allowance_module_address: str,
    chain_id: int,
    rpc_url: str,
    nonce: int | None = None,
) -> str:
    """Enable the Allowance Module on a Safe using master wallet for gas.

    The Privy wallet signs the Safe transaction, and the master wallet
    pays for the gas to submit it on-chain.
    """
    # enableModule(address module)
    enable_selector = keccak(text="enableModule(address)")[:4]
    enable_data = enable_selector + encode(["address"], [allowance_module_address])

    # Get Safe nonce from blockchain if not provided
    if nonce is not None:
        safe_nonce = nonce
    else:
        safe_nonce = await _get_safe_nonce(safe_address, rpc_url)

    # Calculate Safe transaction hash
    safe_tx_hash = _get_safe_tx_hash(
        safe_address=safe_address,
        to=safe_address,  # Call Safe itself to enable module
        value=0,
        data=enable_data,
        nonce=safe_nonce,
        chain_id=chain_id,
    )

    # Sign the transaction hash with Privy wallet
    signature_hex = await privy_client.sign_hash(privy_wallet_id, safe_tx_hash)

    # Parse signature and adjust v value for Safe
    sig_bytes = bytes.fromhex(
        signature_hex[2:] if signature_hex.startswith("0x") else signature_hex
    )
    r = sig_bytes[:32]
    s = sig_bytes[32:64]
    v = sig_bytes[64]
    # Safe expects v to be 27 or 28, but some signers return 0 or 1
    if v < 27:
        v += 27
    signature = r + s + bytes([v])

    # Encode execTransaction with the signature
    exec_selector = keccak(
        text="execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)"
    )[:4]

    exec_data = exec_selector + encode(
        [
            "address",
            "uint256",
            "bytes",
            "uint8",
            "uint256",
            "uint256",
            "uint256",
            "address",
            "address",
            "bytes",
        ],
        [
            to_checksum_address(safe_address),  # to: Safe itself
            0,  # value
            enable_data,  # data
            0,  # operation: 0 = Call
            0,  # safeTxGas
            0,  # baseGas
            0,  # gasPrice
            "0x0000000000000000000000000000000000000000",  # gasToken
            "0x0000000000000000000000000000000000000000",  # refundReceiver
            signature,
        ],
    )

    # Use master wallet to send the transaction
    tx_hash = await _send_safe_transaction_with_master_wallet(
        safe_address=safe_address,
        exec_data=exec_data,
        chain_id=chain_id,
        rpc_url=rpc_url,
    )

    return tx_hash


async def _set_spending_limit(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    safe_address: str,
    owner_address: str,
    delegate_address: str,
    token_address: str,
    allowance_amount: int,
    reset_time_minutes: int,
    allowance_module_address: str,
    chain_id: int,
    rpc_url: str,
    nonce: int | None = None,
) -> str:
    """Set a spending limit via the Allowance Module using master wallet for gas.

    The Privy wallet signs the Safe transaction, and the master wallet
    pays for the gas to submit it on-chain.
    """
    # First, add delegate: addDelegate(address delegate)
    add_delegate_selector = keccak(text="addDelegate(address)")[:4]
    add_delegate_data = add_delegate_selector + encode(["address"], [delegate_address])

    # Then, set allowance: setAllowance(address delegate, address token, uint96 allowanceAmount, uint16 resetTimeMin, uint32 resetBaseMin)
    set_allowance_selector = keccak(
        text="setAllowance(address,address,uint96,uint16,uint32)"
    )[:4]
    set_allowance_data = set_allowance_selector + encode(
        ["address", "address", "uint96", "uint16", "uint32"],
        [
            delegate_address,
            token_address,
            allowance_amount,
            reset_time_minutes,
            0,  # resetBaseMin
        ],
    )

    # Use MultiSend to batch both calls
    # Encode for MultiSend: operation (1 byte) + to (20 bytes) + value (32 bytes) + dataLength (32 bytes) + data
    def encode_multi_send_tx(to: str, value: int, data: bytes) -> bytes:
        return (
            bytes([0])  # operation: 0 = Call
            + bytes.fromhex(to[2:])  # to address
            + value.to_bytes(32, "big")  # value
            + len(data).to_bytes(32, "big")  # data length
            + data  # data
        )

    multi_send_txs = encode_multi_send_tx(
        allowance_module_address, 0, add_delegate_data
    ) + encode_multi_send_tx(allowance_module_address, 0, set_allowance_data)

    # multiSend(bytes transactions)
    multi_send_selector = keccak(text="multiSend(bytes)")[:4]
    multi_send_data = multi_send_selector + encode(["bytes"], [multi_send_txs])

    # Get Safe nonce from blockchain if not provided
    if nonce is not None:
        safe_nonce = nonce
    else:
        safe_nonce = await _get_safe_nonce(safe_address, rpc_url)

    # Calculate Safe transaction hash for the MultiSend call
    # Note: We use MULTI_SEND_CALL_ONLY_ADDRESS with DelegateCall (operation=1)
    safe_tx_hash = _get_safe_tx_hash(
        safe_address=safe_address,
        to=MULTI_SEND_CALL_ONLY_ADDRESS,
        value=0,
        data=multi_send_data,
        nonce=safe_nonce,
        chain_id=chain_id,
        operation=1,  # DelegateCall for MultiSend
    )

    # Sign the transaction hash with Privy wallet
    signature_hex = await privy_client.sign_hash(privy_wallet_id, safe_tx_hash)

    # Parse signature and adjust v value for Safe
    sig_bytes = bytes.fromhex(
        signature_hex[2:] if signature_hex.startswith("0x") else signature_hex
    )
    r = sig_bytes[:32]
    s = sig_bytes[32:64]
    v = sig_bytes[64]
    if v < 27:
        v += 27
    signature = r + s + bytes([v])

    # Encode execTransaction with signature
    exec_selector = keccak(
        text="execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)"
    )[:4]

    exec_data = exec_selector + encode(
        [
            "address",
            "uint256",
            "bytes",
            "uint8",
            "uint256",
            "uint256",
            "uint256",
            "address",
            "address",
            "bytes",
        ],
        [
            MULTI_SEND_CALL_ONLY_ADDRESS,  # to
            0,  # value
            multi_send_data,  # data
            1,  # operation: 1 = DelegateCall for MultiSend
            0,  # safeTxGas
            0,  # baseGas
            0,  # gasPrice
            "0x0000000000000000000000000000000000000000",  # gasToken
            "0x0000000000000000000000000000000000000000",  # refundReceiver
            signature,
        ],
    )

    # Use master wallet to send the transaction
    tx_hash = await _send_safe_transaction_with_master_wallet(
        safe_address=safe_address,
        exec_data=exec_data,
        chain_id=chain_id,
        rpc_url=rpc_url,
    )

    return tx_hash


# =============================================================================
# Gasless Transaction Support (Relayer Pattern)
# =============================================================================


async def execute_gasless_transaction(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    safe_address: str,
    to: str,
    value: int,
    data: bytes,
    network_id: str,
    rpc_url: str,
) -> str:
    """
    Execute a Safe transaction with gas paid by the Master Wallet (Relayer pattern).

    This enables gasless transactions for Safe wallets:
    1. The Safe owner (Privy wallet) signs the transaction hash off-chain
    2. The Master Wallet submits the signed transaction on-chain and pays for gas
    3. The Safe executes the transaction

    This is ideal for scenarios where Safe wallet owners don't hold ETH for gas,
    such as User-to-Agent USDC transfers.

    Args:
        privy_client: Initialized Privy client
        privy_wallet_id: The Privy wallet ID (owner of the Safe)
        safe_address: The Safe smart account address
        to: Target address for the transaction
        value: ETH value to send (in wei, usually 0 for ERC20 transfers)
        data: Transaction calldata (e.g., encoded ERC20 transfer)
        network_id: Network identifier (e.g., "base-mainnet")
        rpc_url: RPC URL for the network

    Returns:
        Transaction hash of the executed transaction

    Raises:
        ValueError: If network is not supported
        IntentKitAPIError: If transaction execution fails
    """

    chain_config = CHAIN_CONFIGS.get(network_id)
    if not chain_config:
        raise ValueError(f"Unsupported network: {network_id}")

    # Get Safe nonce from blockchain
    safe_nonce = await _get_safe_nonce(safe_address, rpc_url)

    # Calculate Safe transaction hash (EIP-712)
    safe_tx_hash = _get_safe_tx_hash(
        safe_address=safe_address,
        to=to,
        value=value,
        data=data,
        nonce=safe_nonce,
        chain_id=chain_config.chain_id,
    )

    logger.debug(
        f"Gasless tx: safe={safe_address}, to={to}, value={value}, "
        f"nonce={safe_nonce}, hash={safe_tx_hash.hex()}"
    )

    # Sign the transaction hash with Privy wallet (off-chain, no gas)
    signature_hex = await privy_client.sign_hash(privy_wallet_id, safe_tx_hash)

    # Parse signature and adjust v value for Safe
    sig_bytes = bytes.fromhex(
        signature_hex[2:] if signature_hex.startswith("0x") else signature_hex
    )
    r = sig_bytes[:32]
    s = sig_bytes[32:64]
    v = sig_bytes[64]
    # Safe expects v to be 27 or 28, but some signers return 0 or 1
    if v < 27:
        v += 27
    signature = r + s + bytes([v])

    # Encode execTransaction with the signature
    exec_selector = keccak(
        text="execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)"
    )[:4]

    exec_data = exec_selector + encode(
        [
            "address",
            "uint256",
            "bytes",
            "uint8",
            "uint256",
            "uint256",
            "uint256",
            "address",
            "address",
            "bytes",
        ],
        [
            to_checksum_address(to),
            value,
            data,
            0,  # operation: 0 = Call
            0,  # safeTxGas
            0,  # baseGas
            0,  # gasPrice
            "0x0000000000000000000000000000000000000000",  # gasToken
            "0x0000000000000000000000000000000000000000",  # refundReceiver
            signature,
        ],
    )

    # Use Master Wallet to relay the transaction (pays for gas)
    tx_hash = await _send_safe_transaction_with_master_wallet(
        safe_address=safe_address,
        exec_data=exec_data,
        chain_id=chain_config.chain_id,
        rpc_url=rpc_url,
    )

    logger.info(
        f"Gasless transaction executed: Safe={safe_address}, To={to}, Value={value}, TxHash={tx_hash}"
    )

    return tx_hash


async def _execute_allowance_transfer_gasless(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    privy_wallet_address: str,
    safe_address: str,
    token_address: str,
    to: str,
    amount: int,
    network_id: str,
    rpc_url: str,
) -> str:
    """
    Execute a token transfer via Allowance Module with gas paid by Master Wallet.

    This enforces the spending limits defined in the Allowance Module.
    """
    chain_config = CHAIN_CONFIGS.get(network_id)
    if not chain_config:
        raise ValueError(f"Unsupported network: {network_id}")

    # Get allowance module address
    allowance_module = chain_config.allowance_module_address

    # Need an instance of SafeWalletProvider helper methods to reuse logic
    # or we can make those methods static/standalone.
    # Currently _get_allowance_nonce, _generate_transfer_hash, _encode_execute_allowance_transfer
    # are instance methods of SafeWalletProvider or private helper methods in the module?
    # Checking existing code... they are methods of SafeWalletProvider.
    # But we are in a standalone function here.
    # We should instantiate a temporary provider or refactor/copy the helpers.
    # Instantiating is cleaner if it doesn't have side effects.
    # SafeWalletProvider init is lightweight.
    safe_provider = SafeWalletProvider(
        privy_wallet_id=privy_wallet_id,
        privy_wallet_address=privy_wallet_address,
        safe_address=safe_address,
        network_id=network_id,
        rpc_url=rpc_url,
    )

    # Get nonce
    nonce = await safe_provider._get_allowance_nonce(
        rpc_url, allowance_module, token_address
    )

    # Generate hash
    transfer_hash = await safe_provider._generate_transfer_hash(
        rpc_url=rpc_url,
        allowance_module=allowance_module,
        token_address=token_address,
        to=to,
        amount=amount,
        nonce=nonce,
    )

    # Sign hash with Privy (Delegate)
    signature = await privy_client.sign_hash(privy_wallet_id, transfer_hash)

    # Encode execution data
    exec_data = safe_provider._encode_execute_allowance_transfer(
        token_address=token_address,
        to=to,
        amount=amount,
        signature=signature,
    )

    try:
        # Send transaction to Allowance Module via Master Wallet
        tx_hash = await _send_transaction_with_master_wallet(
            to=allowance_module,
            data=exec_data,
            chain_id=chain_config.chain_id,
            rpc_url=rpc_url,
            gas_limit=200000,  # Allowance transfers are cheaper
        )
        return tx_hash

    except IntentKitAPIError as e:
        # Try to interpret the error
        # Allowance Module errors:
        # GS013: Safe Transaction failed (if module calls execTransactionFromModule and that fails)
        # But here we call the Module directly.
        # Common errors: "L1" (Limit exceeded), "A1" (Transfer failed)
        err_msg = str(e)
        logger.error(f"Allowance transfer gasless failed: {err_msg}")

        # If the transaction failed on-chain, it's likely a limit issue or balance issue
        # We assume limit exceeded for clarity if it's a generic failure during this specific op
        if "TxFailed" in str(e.key) or "execution reverted" in err_msg.lower():
            raise IntentKitAPIError(
                400,
                "SpendingLimitExceeded",
                f"Transaction failed. This likely means the weekly spending limit has been exceeded or the Safe has insufficient funds. (Amount: {amount / 1e6} USDC)",
            ) from e
        raise


async def transfer_erc20_gasless(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    safe_address: str,
    token_address: str,
    to: str,
    amount: int,
    network_id: str,
    rpc_url: str,
    privy_wallet_address: str | None = None,
    force_admin_execution: bool = False,
) -> str:
    """
    Transfer ERC20 tokens from a Safe wallet with gas paid by Master Wallet.

    Smart Fallback:
    1. If Allowance Module is enabled and privy_wallet_address is provided,
       uses _execute_allowance_transfer_gasless (enforces limits).
    2. Otherwise, falls back to execute_gasless_transaction (owner direct).

    Args:
        force_admin_execution: If True, bypass allowance module and use direct owner transfer
                             even if the module is enabled.
    """
    chain_config = CHAIN_CONFIGS.get(network_id)
    if not chain_config:
        raise ValueError(f"Unsupported network: {network_id}")

    # Check if Allowance Module is enabled
    allowance_module = chain_config.allowance_module_address
    is_enabled = await _is_module_enabled(
        rpc_url=rpc_url,
        safe_address=safe_address,
        module_address=allowance_module,
    )

    if is_enabled and not force_admin_execution:
        # If address not provided, try to fetch it from Privy
        effective_wallet_address = privy_wallet_address
        if not effective_wallet_address:
            try:
                wallet = await privy_client.get_wallet(privy_wallet_id)
                effective_wallet_address = wallet.address
                logger.info(
                    f"Fetched Privy wallet address {effective_wallet_address} for ID {privy_wallet_id}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to fetch wallet address for {privy_wallet_id}: {e}"
                )

        if effective_wallet_address:
            logger.info("Allowance Module enabled, using allowance transfer (gasless)")
            return await _execute_allowance_transfer_gasless(
                privy_client=privy_client,
                privy_wallet_id=privy_wallet_id,
                privy_wallet_address=effective_wallet_address,
                safe_address=safe_address,
                token_address=token_address,
                to=to,
                amount=amount,
                network_id=network_id,
                rpc_url=rpc_url,
            )
        else:
            logger.warning(
                "Allowance Module enabled but privy_wallet_address missing and fetch failed. "
                "The transfer might fail if the Owner is not a Delegate. "
                "Falling back to Owner direct transfer."
            )

    if is_enabled and force_admin_execution:
        logger.info(
            "Allowance Module enabled but force_admin_execution is True, bypassing allowance (gasless)"
        )

    logger.info("Using direct owner transfer (gasless)")
    # Fallback to direct owner transfer (gasless)
    # Encode ERC20 transfer call
    transfer_selector = keccak(text="transfer(address,uint256)")[:4]
    transfer_data = transfer_selector + encode(
        ["address", "uint256"],
        [to_checksum_address(to), amount],
    )

    return await execute_gasless_transaction(
        privy_client=privy_client,
        privy_wallet_id=privy_wallet_id,
        safe_address=safe_address,
        to=token_address,
        value=0,
        data=transfer_data,
        network_id=network_id,
        rpc_url=rpc_url,
    )


# =============================================================================
# Main Entry Points
# =============================================================================


async def create_privy_safe_wallet(
    agent_id: str,
    network_id: str = "base-mainnet",
    rpc_url: str | None = None,
    weekly_spending_limit_usdc: float | None = None,
    existing_privy_wallet_id: str | None = None,
    existing_privy_wallet_address: str | None = None,
) -> dict[str, Any]:
    """
    Create a Privy server wallet and deploy a Safe smart account.

    This is the main entry point for creating a new agent wallet with
    Safe smart account and optional spending limits.

    Supports recovery mode: if a previous attempt created a Privy wallet but
    failed to deploy the Safe, pass the existing wallet details to resume
    without creating a duplicate Privy wallet.

    Args:
        agent_id: Unique identifier for the agent (used as idempotency key)
        network_id: The network to use (default: base-mainnet)
        rpc_url: Optional RPC URL override
        weekly_spending_limit_usdc: Optional weekly USDC spending limit
        existing_privy_wallet_id: Existing Privy wallet ID for recovery mode
        existing_privy_wallet_address: Existing Privy wallet address for recovery mode

    Returns:
        dict: Metadata including:
            - privy_wallet_id: The Privy wallet ID
            - privy_wallet_address: The Privy EOA address (owner/signer)
            - smart_wallet_address: The Safe smart account address
            - provider: "safe"
            - network_id: The network ID
            - chain_id: The chain ID
            - deployment_info: Deployment transaction details
    """
    chain_config = CHAIN_CONFIGS.get(network_id)
    if not chain_config:
        raise ValueError(f"Unsupported network: {network_id}")

    # Get RPC URL
    effective_rpc_url = rpc_url or chain_config.rpc_url
    if not effective_rpc_url:
        raise ValueError(f"No RPC URL configured for {network_id}")

    privy_client = PrivyClient()

    # 1. Get or create Privy Wallet (EOA that will own the Safe)
    # Recovery mode: use existing wallet if provided (avoids creating duplicate wallets)
    if existing_privy_wallet_id and existing_privy_wallet_address:
        logger.info(
            f"Recovery mode: using existing Privy wallet {existing_privy_wallet_id}"
        )
        privy_wallet_id = existing_privy_wallet_id
        privy_wallet_address = existing_privy_wallet_address
    else:
        privy_wallet = await privy_client.create_wallet()
        privy_wallet_id = privy_wallet.id
        privy_wallet_address = privy_wallet.address

    # 2. Deploy Safe and configure allowance module
    deployment_info = await deploy_safe_with_allowance(
        privy_client=privy_client,
        privy_wallet_id=privy_wallet_id,
        privy_wallet_address=privy_wallet_address,
        network_id=network_id,
        rpc_url=effective_rpc_url,
        weekly_spending_limit_usdc=weekly_spending_limit_usdc,
    )

    return {
        "privy_wallet_id": privy_wallet_id,
        "privy_wallet_address": privy_wallet_address,
        "smart_wallet_address": deployment_info["safe_address"],
        "provider": "safe",
        "network_id": network_id,
        "chain_id": chain_config.chain_id,
        "salt_nonce": deployment_info["salt_nonce"],
        "deployment_info": deployment_info,
    }


def get_wallet_provider(
    privy_wallet_data: dict[str, Any],
    rpc_url: str | None = None,
) -> SafeWalletProvider:
    """
    Create a SafeWalletProvider from stored wallet data.

    This is used to restore a wallet provider from persisted agent data.

    Args:
        privy_wallet_data: The stored wallet metadata
        rpc_url: Optional RPC URL override

    Returns:
        SafeWalletProvider instance ready for transactions
    """
    return SafeWalletProvider(
        privy_wallet_id=privy_wallet_data["privy_wallet_id"],
        privy_wallet_address=privy_wallet_data["privy_wallet_address"],
        safe_address=privy_wallet_data["smart_wallet_address"],
        network_id=privy_wallet_data.get("network_id", "base-mainnet"),
        rpc_url=rpc_url,
    )


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
        import asyncio
        import threading

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
        from eth_account.datastructures import SignedMessage

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
        from eth_account.datastructures import SignedMessage

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
        from eth_account.datastructures import SignedMessage

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
