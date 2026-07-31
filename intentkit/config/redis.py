"""Redis client module for IntentKit."""

import logging

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from intentkit.utils.readiness import wait_until_ready

logger = logging.getLogger(__name__)

# Socket timeouts are set explicitly rather than inherited. redis-py 7 defaults
# both to None (block forever), redis-py 8 to 5s; pinning them here keeps the
# behaviour identical across that bump and bounds a hung connection. Every
# command this service issues is a small key read/write -- there are no blocking
# commands (BLPOP/BRPOP/XREAD) anywhere in the codebase -- so 5s is far above
# the worst legitimate round trip.
REDIS_SOCKET_TIMEOUT = 5.0
REDIS_CONNECT_TIMEOUT = 5.0

# Global Redis client instance
_redis_client: Redis | None = None


async def init_redis(
    host: str,
    port: int = 6379,
    db: int = 0,
    password: str | None = None,
    ssl: bool = False,
    encoding: str = "utf-8",
    decode_responses: bool = True,
    socket_timeout: float = REDIS_SOCKET_TIMEOUT,
    socket_connect_timeout: float = REDIS_CONNECT_TIMEOUT,
) -> Redis:
    """Initialize the Redis client.

    Args:
        host: Redis host
        port: Redis port (default: 6379)
        db: Redis database number (default: 0)
        password: Redis password (default: None)
        ssl: Whether to use SSL (default: False)
        encoding: Response encoding (default: utf-8)
        decode_responses: Whether to decode responses (default: True)
        socket_timeout: Per-command socket timeout in seconds
        socket_connect_timeout: Connection establishment timeout in seconds

    Returns:
        Redis: The initialized Redis client
    """
    global _redis_client

    if _redis_client is not None:
        logger.info("Redis client already initialized")
        return _redis_client

    try:
        logger.info("Initializing Redis client at %s:%s", host, port)
        client = Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            ssl=ssl,
            encoding=encoding,
            decode_responses=decode_responses,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
        )

        # Test the connection. Services restart in arbitrary order, so Redis
        # may still be booting; retry instead of failing the start.
        await wait_until_ready(
            "Redis", client.ping, (RedisConnectionError, RedisTimeoutError)
        )
        _redis_client = client
        logger.info("Redis client initialized successfully")
        return client
    except Exception as e:
        logger.error("Failed to initialize Redis client: %s", e)
        raise


def get_redis() -> Redis:
    """Get the Redis client.

    Returns:
        Redis: The Redis client

    Raises:
        RuntimeError: If the Redis client is not initialized
    """
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis first.")
    return _redis_client


DEFAULT_HEARTBEAT_TTL = 16 * 60


async def send_heartbeat(redis_client: Redis, name: str) -> None:
    """Set a heartbeat key in Redis that expires after 16 minutes.

    Args:
        redis_client: Redis client instance
        name: Name identifier for the heartbeat
    """
    try:
        key = f"intentkit:heartbeat:{name}"
        await redis_client.set(key, 1, ex=DEFAULT_HEARTBEAT_TTL)
    except Exception as e:
        logger.error("Failed to send heartbeat for %s: %s", name, e)


async def check_heartbeat(redis_client: Redis, name: str) -> bool:
    """Check if a heartbeat key exists in Redis.

    Args:
        redis_client: Redis client instance
        name: Name identifier for the heartbeat

    Returns:
        bool: True if heartbeat exists, False otherwise
    """
    import asyncio

    key = f"intentkit:heartbeat:{name}"
    retries = 3
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            exists = await redis_client.exists(key)
            return bool(exists)
        except Exception as e:
            # WARNING per attempt: transient blips must not reach the alert
            # channel (which forwards ERROR+); only exhausting all retries is
            # worth an alert.
            last_exc = e
            logger.warning(
                "Error checking heartbeat for %s (attempt %s/%s): %s",
                name,
                attempt + 1,
                retries,
                e,
            )
            if attempt < retries - 1:  # Don't sleep on the last attempt
                await asyncio.sleep(5)  # Wait 5 seconds before retrying

    logger.error(
        "Heartbeat check for %s failed after %s attempts: %s", name, retries, last_exc
    )
    return False


async def clean_heartbeat(redis_client: Redis, name: str) -> None:
    """Remove a heartbeat key from Redis.

    Args:
        redis_client: Redis client instance
        name: Name identifier for the heartbeat to remove
    """
    try:
        key = f"intentkit:heartbeat:{name}"
        await redis_client.delete(key)
        logger.info("Removed heartbeat for %s", name)
    except Exception as e:
        logger.error("Failed to remove heartbeat for %s: %s", name, e)
