import asyncio
import logging
import time

from eth_account import Account
from eth_utils import to_checksum_address
from web3 import AsyncWeb3

from intentkit.config.config import config
from intentkit.config.redis import get_redis
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


# =============================================================================
# Distributed Nonce Manager (Redis-based)
# =============================================================================

NONCE_LOCK_TTL = 30  # Lock expires after 30 seconds (prevents deadlocks)
NONCE_KEY_TTL = 3600  # Nonce cache expires after 1 hour


class WalletNonceManager:
    """Distributed per-address nonce manager using Redis.

    Prevents nonce collisions when several workers/container replicas — or,
    for team wallets, several agents — send from the same EOA concurrently.

    Uses Redis for:
    - nonce storage (shared across all processes)
    - distributed locking (SETNX pattern with TTL)
    """

    address: str
    network_id: str
    _nonce_key: str
    _lock_key: str

    def __init__(self, address: str, network_id: str):
        # Nonces are tracked independently per chain, so the same address on
        # two networks must never share a counter.
        self.address = to_checksum_address(address)
        self.network_id = network_id
        self._nonce_key = f"intentkit:wallet:nonce:{network_id}:{address.lower()}"
        self._lock_key = f"intentkit:wallet:lock:{network_id}:{address.lower()}"

    async def acquire_lock(self, timeout: float = 10.0) -> bool:
        """Acquire distributed lock with timeout.

        Args:
            timeout: Maximum seconds to wait for lock acquisition

        Returns:
            True if lock acquired, False if timeout
        """
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
                to_checksum_address(self.address), "pending"
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
            to_checksum_address(self.address), "pending"
        )
        await redis.set(self._nonce_key, str(blockchain_nonce), ex=NONCE_KEY_TTL)
        logger.info("Reset wallet %s nonce to %s", self.address, blockchain_nonce)


# Per-address manager instances; state lives in Redis, these are just handles.
_nonce_managers: dict[str, WalletNonceManager] = {}


def get_wallet_nonce_manager(address: str, network_id: str) -> WalletNonceManager:
    """Get or create the nonce manager for a wallet address on a network."""
    key = f"{network_id}:{address.lower()}"
    manager = _nonce_managers.get(key)
    if manager is None:
        manager = WalletNonceManager(address, network_id)
        _nonce_managers[key] = manager
    return manager


def get_nonce_manager(network_id: str) -> WalletNonceManager:
    """Get or create the nonce manager for the master wallet on a network."""
    if not config.master_wallet_private_key:
        raise IntentKitAPIError(
            500, "ConfigError", "MASTER_WALLET_PRIVATE_KEY not configured"
        )
    master_account = Account.from_key(config.master_wallet_private_key)
    return get_wallet_nonce_manager(str(master_account.address), network_id)
