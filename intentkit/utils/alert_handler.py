"""
Rate-limited logging handler for sending alerts to Telegram/Slack.

This module provides a logging handler that sends ERROR+ level logs to
Telegram or Slack with rate limiting to prevent message flooding.

Uses Redis for distributed rate limiting with sliding window algorithm.
"""

import logging
import time
from queue import Queue
from threading import Thread
from typing import Callable, override

import httpx
from redis import Redis

from intentkit.utils.slack_alert import send_slack_message

# Global sync Redis client for alert handler
_sync_redis_client: Redis | None = None

# Redis key prefix for rate limiting
RATE_LIMIT_KEY_PREFIX = "intentkit:alert:rate_limit"


def init_alert_redis(
    host: str,
    port: int = 6379,
    db: int = 0,
    password: str | None = None,
    ssl: bool = False,
) -> Redis:
    """Initialize synchronous Redis client for alert handler.

    Args:
        host: Redis host
        port: Redis port (default: 6379)
        db: Redis database number (default: 0)
        password: Redis password (default: None)
        ssl: Whether to use SSL (default: False)

    Returns:
        Redis: The initialized sync Redis client
    """
    global _sync_redis_client

    if _sync_redis_client is not None:
        return _sync_redis_client

    _sync_redis_client = Redis(
        host=host,
        port=port,
        db=db,
        password=password,
        ssl=ssl,
        decode_responses=True,
    )
    # Test connection
    _ = _sync_redis_client.ping()
    return _sync_redis_client


def get_alert_redis() -> Redis:
    """Get the sync Redis client for alert handler.

    Returns:
        Redis client

    Raises:
        RuntimeError: If the Redis client is not initialized
    """
    if _sync_redis_client is None:
        raise RuntimeError("Alert Redis client not initialized. Call init_alert_redis.")
    return _sync_redis_client


class RateLimitedAlertHandler(logging.Handler):
    """
    A logging handler that sends ERROR+ level logs to Telegram/Slack
    with rate limiting using Redis (e.g., max 3 messages per minute).

    Uses a background thread to avoid blocking the main application.
    """

    send_func: Callable[[str], None]
    max_messages: int
    time_window: int
    _dropped_count: int
    _queue: Queue[str]
    _worker: Thread
    _rate_limit_key: str

    def __init__(
        self,
        send_func: Callable[[str], None],
        max_messages: int = 3,
        time_window: int = 60,  # seconds
        level: int = logging.ERROR,
        rate_limit_key: str = "default",
    ):
        super().__init__(level=level)
        self.send_func = send_func
        self.max_messages = max_messages
        self.time_window = time_window
        self._rate_limit_key = f"{RATE_LIMIT_KEY_PREFIX}:{rate_limit_key}"

        # Count of dropped messages (tracked locally for efficiency)
        self._dropped_count = 0

        # Background send queue
        self._queue = Queue()
        self._worker = Thread(target=self._process_queue, daemon=True)
        self._worker.start()

    def _is_rate_limited(self) -> bool:
        """Check if rate limit is exceeded using Redis sliding window."""
        redis = get_alert_redis()

        now = time.time()
        window_start = now - self.time_window

        # Use Redis pipeline for atomic operations
        pipe = redis.pipeline()

        # Remove old entries outside the window
        _ = pipe.zremrangebyscore(self._rate_limit_key, 0, window_start)

        # Count current entries in window
        _ = pipe.zcard(self._rate_limit_key)

        # Execute pipeline
        results = pipe.execute()
        current_count = results[1]

        # Check if limit exceeded
        if current_count >= self.max_messages:
            self._dropped_count += 1
            return True

        # Add current timestamp to sorted set
        _ = redis.zadd(self._rate_limit_key, {str(now): now})

        # Set expiry on the key to auto-cleanup
        _ = redis.expire(self._rate_limit_key, self.time_window + 10)

        return False

    def _process_queue(self) -> None:
        """Background thread processes the send queue."""
        while True:
            msg = self._queue.get()
            try:
                self.send_func(msg)
            except Exception as e:
                # Cannot use logger here to avoid infinite loop
                print(f"[AlertHandler] Failed to send notification: {e}")
            finally:
                self._queue.task_done()

    @override
    def emit(self, record: logging.LogRecord) -> None:
        """Process log record."""
        if self._is_rate_limited():
            return

        try:
            msg = self.format(record)

            # Atomic read-and-reset for local counter
            dropped_to_report = 0
            if self._dropped_count > 0:
                dropped_to_report = self._dropped_count
                self._dropped_count = 0

            # If there are dropped messages, add a notice
            if dropped_to_report > 0:
                msg = f"[⚠️ {dropped_to_report} messages dropped due to rate limit]\n\n{msg}"

            # Non-blocking put into queue
            self._queue.put_nowait(msg)
        except Exception:
            self.handleError(record)


def create_telegram_sender(bot_token: str, chat_id: str) -> Callable[[str], None]:
    """
    Create a Telegram sender function.

    Args:
        bot_token: Telegram Bot Token (obtained from @BotFather)
        chat_id: Target Chat ID (can be user, group, or channel)

    Returns:
        Sender function
    """

    # Create a persistent client with timeout
    client = httpx.Client(timeout=10)

    def send(message: str) -> None:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        try:
            _ = client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message[:4096],  # Telegram message length limit
                },
            ).raise_for_status()
        except Exception:
            # Re-raise to be handled by caller
            raise

    return send


def create_slack_sender() -> Callable[[str], None]:
    """
    Create a Slack sender function (reuses existing slack_alert module).
    """

    def send(message: str) -> None:
        send_slack_message(message)

    return send


def setup_alert_handler(
    redis_host: str,
    telegram_bot_token: str | None = None,
    telegram_chat_id: str | None = None,
    slack_enabled: bool = False,
    redis_port: int = 6379,
    redis_db: int = 0,
    redis_password: str | None = None,
    redis_ssl: bool = False,
    max_messages: int = 3,
    time_window: int = 60,
    level: int = logging.ERROR,
    logger_name: str | None = None,
) -> RateLimitedAlertHandler | None:
    """
    Set up alert handler with priority: Telegram > Slack.

    Args:
        telegram_bot_token: Telegram Bot Token
        telegram_chat_id: Target Telegram Chat ID
        slack_enabled: Whether Slack is configured (uses existing slack_alert module)
        redis_host: Redis host for rate limiting
        redis_port: Redis port (default: 6379)
        redis_db: Redis database number (default: 0)
        redis_password: Redis password (default: None)
        redis_ssl: Whether to use SSL (default: False)
        max_messages: Maximum messages within time window
        time_window: Time window in seconds
        level: Log level
        logger_name: Logger name to add handler to, None means root logger

    Returns:
        Created handler instance, or None if no alert service is configured
    """
    send_func: Callable[[str], None] | None = None
    service_name: str = ""

    # Priority: Telegram > Slack
    if telegram_bot_token and telegram_chat_id:
        send_func = create_telegram_sender(telegram_bot_token, telegram_chat_id)
        service_name = "Telegram"
    elif slack_enabled:
        send_func = create_slack_sender()
        service_name = "Slack"

    if send_func is None:
        return None

    # Initialize sync Redis for rate limiting
    if not redis_host:
        raise RuntimeError("Redis host is required for alert handler")
    _ = init_alert_redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
        ssl=redis_ssl,
    )
    print(f"[AlertHandler] Redis initialized at {redis_host}:{redis_port}")

    handler = RateLimitedAlertHandler(
        send_func=send_func,
        max_messages=max_messages,
        time_window=time_window,
        level=level,
        rate_limit_key=service_name.lower(),
    )
    handler.setFormatter(
        logging.Formatter("🚨 %(levelname)s | %(name)s\n\n%(message)s")
    )

    target_logger = (
        logging.getLogger(logger_name) if logger_name else logging.getLogger()
    )
    target_logger.addHandler(handler)

    # Log which service is being used (use print to avoid recursion)
    print(
        f"[AlertHandler] Initialized with {service_name} (rate limit: {max_messages}/{time_window}s)"
    )

    return handler
