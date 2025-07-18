#!/usr/bin/env python3
"""
Check if a heartbeat exists in Redis for a given name.

Usage:
  check_heartbeat.py NAME

Returns:
  0 - Heartbeat exists (success)
  1 - Heartbeat does not exist or error occurred
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from intentkit.config.config import config
from intentkit.models.redis import check_heartbeat, get_redis, init_redis

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Initialize Redis and check for heartbeat."""
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} NAME")
        sys.exit(1)

    name = sys.argv[1]
    redis_client = None

    try:
        # Initialize Redis
        if config.redis_host:
            await init_redis(
                host=config.redis_host,
                port=config.redis_port,
                db=config.redis_db,
            )
        else:
            logger.error("Redis host not configured")
            sys.exit(1)

        # Get Redis client
        redis_client = get_redis()

        # Check heartbeat
        exists = await check_heartbeat(redis_client, name)

        if exists:
            logger.info(f"Heartbeat for '{name}' exists")
            return 0  # Success
        else:
            logger.error(f"Heartbeat for '{name}' does not exist")
            return 1  # Failure

    except Exception:
        logger.error(f"Heartbeat for '{name}' does not exist, and there was an error")
        return 1  # General error
    finally:
        # Close Redis connection if it was opened
        if redis_client is not None:
            await redis_client.aclose()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
