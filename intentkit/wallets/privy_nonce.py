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
