"""Local memory endpoints.

Read and edit the memory documents agents maintain automatically. Local
mode is single-user: both the team and the user are "system", so this
exposes the team-scope and user-scope rows of that account. Channel and
cron memories stay internal to their conversations and are not exposed.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from intentkit.core.memory import (
    MemoryWithAgent,
    list_account_memories,
    overwrite_memory,
)
from intentkit.models.memory import Memory

memory_router = APIRouter(tags=["Memory"])

logger = logging.getLogger(__name__)

# Local single-user mode: team and user are both "system"
LOCAL_ID = "system"


class MemoryUpdateRequest(BaseModel):
    # max_length is characters; the byte cap is enforced in overwrite_memory
    content: str = Field(description="Full memory document (markdown)", max_length=4000)


@memory_router.get(
    "/memories",
    operation_id="list_memories",
    summary="List Memories",
)
async def list_memories() -> list[MemoryWithAgent]:
    """List the team-scope and user-scope memories of the local account."""
    return await list_account_memories(LOCAL_ID, LOCAL_ID)


@memory_router.put(
    "/memories/{memory_id}",
    operation_id="update_memory",
    summary="Update Memory",
)
async def update_memory(memory_id: str, request: MemoryUpdateRequest) -> Memory:
    """Overwrite one memory document."""
    return await overwrite_memory(
        memory_id, request.content, team_id=LOCAL_ID, user_id=LOCAL_ID
    )
