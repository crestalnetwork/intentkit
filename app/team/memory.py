"""Team memory endpoints.

Read and edit the memory documents agents maintain automatically: the
team's memories (scope ``team``) and the requesting user's own memories
(scope ``user``). Channel and cron memories stay internal to their
conversations and are not exposed here.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from intentkit.core.memory import (
    MemoryWithAgent,
    list_account_memories,
    overwrite_memory,
)
from intentkit.models.memory import Memory

from app.team.auth import verify_team_member

team_memory_router = APIRouter(tags=["Memory"])

logger = logging.getLogger(__name__)


class MemoryUpdateRequest(BaseModel):
    # max_length is characters; the byte cap is enforced in overwrite_memory
    content: str = Field(description="Full memory document (markdown)", max_length=4000)


@team_memory_router.get(
    "/teams/{team_id}/memories",
    operation_id="list_team_memories",
    summary="List Memories",
)
async def list_team_memories(
    auth: tuple[str, str] = Depends(verify_team_member),
) -> list[MemoryWithAgent]:
    """List the team's memories and the requesting user's own memories."""
    user_id, team_id = auth
    return await list_account_memories(team_id, user_id)


@team_memory_router.put(
    "/teams/{team_id}/memories/{memory_id}",
    operation_id="update_team_memory",
    summary="Update Memory",
)
async def update_team_memory(
    memory_id: str,
    request: MemoryUpdateRequest,
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Memory:
    """Overwrite one memory document (team scope or the user's own)."""
    user_id, team_id = auth
    return await overwrite_memory(
        memory_id, request.content, team_id=team_id, user_id=user_id
    )
