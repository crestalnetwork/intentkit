"""Task registry for tracking running streaming tasks.

Simple module-level registry that maps (agent_id, chat_id) to asyncio.Task[None],
enabling cancellation of in-progress streaming responses.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

# Process-level registry: {(agent_id, chat_id): asyncio.Task[None]}
_running_tasks: dict[tuple[str, str], asyncio.Task[None]] = {}


def register_task(agent_id: str, chat_id: str, task: asyncio.Task[None]) -> None:
    """Register a running streaming task."""
    _running_tasks[(agent_id, chat_id)] = task


def unregister_task(agent_id: str, chat_id: str) -> None:
    """Unregister a streaming task."""
    _running_tasks.pop((agent_id, chat_id), None)


def cancel_task(agent_id: str, chat_id: str) -> bool:
    """Cancel a running streaming task. Returns True if a task was found and cancelled."""
    task = _running_tasks.get((agent_id, chat_id))
    if task is None or task.done():
        return False
    task.cancel()
    logger.info("Cancelled task for agent %s, chat %s", agent_id, chat_id)
    return True
