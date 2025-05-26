"""Redis client module for IntentKit."""

import logging
from typing import Optional

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[Redis] = None


async def init_redis(
    host: str,
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None,
    ssl: bool = False,
    encoding: str = "utf-8",
    decode_responses: bool = True,
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

    Returns:
        Redis: The initialized Redis client
    """
    global _redis_client

    if _redis_client is not None:
        logger.info("Redis client already initialized")
        return _redis_client

    try:
        logger.info(f"Initializing Redis client at {host}:{port}")
        _redis_client = Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            ssl=ssl,
            encoding=encoding,
            decode_responses=decode_responses,
        )
        # Test the connection
        await _redis_client.ping()
        logger.info("Redis client initialized successfully")
        return _redis_client
    except Exception as e:
        logger.error(f"Failed to initialize Redis client: {e}")
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


async def send_heartbeat(redis_client: Redis, name: str) -> None:
    """Set a heartbeat key in Redis that expires after 16 minutes.

    Args:
        redis_client: Redis client instance
        name: Name identifier for the heartbeat
    """
    try:
        key = f"intentkit:heartbeat:{name}"
        await redis_client.set(key, 1, ex=190)  # 190 seconds = 3 minutes
    except Exception as e:
        logger.error(f"Failed to send heartbeat for {name}: {e}")


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

    for attempt in range(retries):
        try:
            exists = await redis_client.exists(key)
            return bool(exists)
        except Exception as e:
            logger.error(
                f"Error checking heartbeat for {name} (attempt {attempt + 1}/{retries}): {e}"
            )
            if attempt < retries - 1:  # Don't sleep on the last attempt
                await asyncio.sleep(5)  # Wait 5 seconds before retrying

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
        logger.info(f"Removed heartbeat for {name}")
    except Exception as e:
        logger.error(f"Failed to remove heartbeat for {name}: {e}")
