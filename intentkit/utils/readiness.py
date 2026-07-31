"""Wait for external dependencies to accept connections at startup.

Container orchestrators restart services in arbitrary order, so an app
container often boots a few seconds before its database, cache, or object
store is reachable. These helpers retry a cheap readiness probe at a fixed
interval, logging at WARNING (which stays out of the alert channel) while
waiting. When the deadline expires the last probe error is re-raised, so the
caller fails exactly as it would have without the wait. The deadline is
checked between attempts, so a slow probe can overshoot it by its own
duration.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

READY_TIMEOUT = 60.0
READY_INTERVAL = 2.0


def _retry_delay(name: str, exc: Exception, deadline: float, interval: float) -> float:
    """Shared retry policy: log the wait and return the sleep duration.

    Re-raises ``exc`` when the next attempt would land past the deadline.
    """
    if time.monotonic() + interval > deadline:
        raise exc
    logger.warning("%s is not ready yet (%s); retrying in %.0fs", name, exc, interval)
    return interval


async def wait_until_ready(
    name: str,
    probe: Callable[[], Awaitable[object]],
    retryable: tuple[type[Exception], ...],
    *,
    timeout: float | None = None,
    interval: float | None = None,
) -> None:
    """Await ``probe()`` until it succeeds, retrying ``retryable`` errors.

    Any exception not in ``retryable`` propagates immediately.
    """
    interval = READY_INTERVAL if interval is None else interval
    deadline = time.monotonic() + (READY_TIMEOUT if timeout is None else timeout)
    while True:
        try:
            _ = await probe()
        except retryable as exc:
            await asyncio.sleep(_retry_delay(name, exc, deadline, interval))
        else:
            return


def wait_until_ready_sync(
    name: str,
    probe: Callable[[], object],
    retryable: tuple[type[Exception], ...],
    *,
    timeout: float | None = None,
    interval: float | None = None,
) -> None:
    """Blocking variant of :func:`wait_until_ready` for sync clients.

    From async code, call via ``asyncio.to_thread``.
    """
    interval = READY_INTERVAL if interval is None else interval
    deadline = time.monotonic() + (READY_TIMEOUT if timeout is None else timeout)
    while True:
        try:
            _ = probe()
        except retryable as exc:
            time.sleep(_retry_delay(name, exc, deadline, interval))
        else:
            return
