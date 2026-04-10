"""Team API agent CRUD endpoints."""

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, Path, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.clients.twitter import unlink_twitter
from intentkit.config.db import get_db, get_session
from intentkit.core.agent import (
    create_agent,
    get_agent_by_id_or_slug,
    patch_agent,
)
from intentkit.core.avatar import generate_avatar
from intentkit.core.lead import invalidate_lead_cache
from intentkit.core.team.membership import check_permission
from intentkit.core.template import render_agent
from intentkit.models.agent import (
    Agent,
    AgentCreate,
    AgentResponse,
    AgentTable,
    AgentUpdate,
)
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent_data import AgentData, AgentDataTable
from intentkit.models.team import TeamRole
from intentkit.utils.error import IntentKitAPIError

from app.team.auth import get_current_user_optional, verify_team_member

team_agent_router = APIRouter()

logger = logging.getLogger(__name__)


async def get_team_agent(agent_id: str, team_id: str) -> Agent:
    """Fetch an agent and verify it belongs to the team.

    Raises:
        IntentKitAPIError 404 if not found or wrong team.
    """
    agent = await get_agent_by_id_or_slug(agent_id)
    if not agent or agent.team_id != team_id:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Agent not found"
        )
    return agent


async def _agent_visible_to(agent: Agent, user_id: str | None) -> bool:
    """Return True if the caller may view this agent.

    Public agents are visible to anyone (unless archived). Team/private agents
    are visible only to members of the owning team, including archived ones.
    """
    is_public = (
        agent.visibility is not None and agent.visibility >= AgentVisibility.PUBLIC
    )
    if is_public and agent.archived_at is None:
        return True
    if not user_id or not agent.team_id:
        return False
    return await check_permission(agent.team_id, user_id, TeamRole.MEMBER)


@team_agent_router.get(
    "/agents/{agent_id}",
    tags=["Agent"],
    operation_id="get_agent",
    summary="Get Agent",
)
async def get_agent_unified(
    agent_id: str = Path(..., description="Agent ID or slug"),
    user_id: str | None = Depends(get_current_user_optional),
) -> Response:
    """Get a single agent by ID or slug.

    Permission is determined by visibility: public agents are accessible
    anonymously; team/private agents require membership in the owning team.
    """
    agent = await get_agent_by_id_or_slug(agent_id)
    if not agent or not await _agent_visible_to(agent, user_id):
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Agent not found"
        )
    agent_data = await AgentData.get(agent.id)
    agent_response = await AgentResponse.from_agent(agent, agent_data)
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@team_agent_router.post(
    "/teams/{team_id}/agents",
    tags=["Team Agent"],
    status_code=201,
    operation_id="team_create_agent",
    summary="Create Agent (Team)",
)
async def create_agent_endpoint(
    agent: AgentUpdate = Body(AgentUpdate, description="Agent configuration"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Create a new agent within the team."""
    user_id, team_id = auth
    new_agent = AgentCreate.model_validate(agent)
    new_agent.owner = user_id
    new_agent.team_id = team_id

    if not new_agent.picture:
        try:
            generated_avatar = await generate_avatar(new_agent.id, new_agent)
            if generated_avatar:
                new_agent.picture = generated_avatar
        except Exception as e:
            logger.error("Failed to auto-generate avatar: %s", e)

    latest_agent, agent_data = await create_agent(new_agent)
    invalidate_lead_cache(team_id)

    agent_response = await AgentResponse.from_agent(latest_agent, agent_data)
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
        status_code=201,
    )


@team_agent_router.get(
    "/teams/{team_id}/agents",
    tags=["Team Agent"],
    operation_id="team_get_agents",
    summary="List Agents (Team)",
)
async def get_agents(
    db: AsyncSession = Depends(get_db),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> list[AgentResponse]:
    """Get all non-archived agents for the team."""
    _user_id, team_id = auth

    agents = (
        await db.scalars(
            select(AgentTable).where(
                AgentTable.team_id == team_id,
                AgentTable.archived_at.is_(None),
            )
        )
    ).all()

    agent_ids = [agent.id for agent in agents]
    agent_data_list = await db.scalars(
        select(AgentDataTable).where(AgentDataTable.id.in_(agent_ids))
    )
    agent_data_map = {data.id: data for data in agent_data_list}

    rendered_agents = await asyncio.gather(
        *[render_agent(Agent.model_validate(a)) for a in agents]
    )

    response_tasks = []
    for agent in rendered_agents:
        agent_data = (
            AgentData.model_validate(agent_data_map.get(agent.id))
            if agent.id in agent_data_map
            else None
        )
        response_tasks.append(AgentResponse.from_agent(agent, agent_data))

    return await asyncio.gather(*response_tasks)


@team_agent_router.get(
    "/teams/{team_id}/agents/{agent_id}",
    tags=["Team Agent"],
    operation_id="team_get_agent",
    summary="Get Agent (Team)",
)
async def get_agent(
    agent_id: str = Path(..., description="Agent ID or slug"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Get a single agent by ID or slug within the team."""
    _user_id, team_id = auth
    agent = await get_team_agent(agent_id, team_id)
    agent_data = await AgentData.get(agent.id)
    agent_response = await AgentResponse.from_agent(agent, agent_data)
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@team_agent_router.get(
    "/teams/{team_id}/agents/{agent_id}/editable",
    tags=["Team Agent"],
    operation_id="team_get_agent_editable",
    summary="Get Agent Editable (Team)",
)
async def get_agent_editable(
    agent_id: str = Path(..., description="Agent ID or slug"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Get agent with full editable fields within the team."""
    _user_id, team_id = auth
    agent = await get_team_agent(agent_id, team_id)
    editable_agent = AgentUpdate.model_validate(agent)
    return Response(
        content=editable_agent.model_dump_json(),
        media_type="application/json",
    )


@team_agent_router.patch(
    "/teams/{team_id}/agents/{agent_id}",
    tags=["Team Agent"],
    operation_id="team_patch_agent",
    summary="Patch Agent (Team)",
)
async def patch_agent_endpoint(
    agent_id: str = Path(..., description="Agent ID"),
    agent: AgentUpdate = Body(AgentUpdate, description="Agent patch configuration"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Patch an existing agent within the team."""
    _user_id, team_id = auth
    existing_agent = await get_team_agent(agent_id, team_id)

    update_fields = agent.model_dump(exclude_unset=True)
    picture_explicitly_set = "picture" in update_fields and update_fields["picture"]
    if not picture_explicitly_set:
        if not existing_agent.picture:
            try:
                generated_avatar = await generate_avatar(agent_id, agent)
                if generated_avatar:
                    agent.picture = generated_avatar
            except Exception as e:
                logger.error("Failed to auto-generate avatar: %s", e)

    latest_agent, agent_data = await patch_agent(agent_id, agent)

    # Invalidate lead cache when purpose changes, so lead agent rebuilds sub-agents list
    if "purpose" in update_fields:
        invalidate_lead_cache(team_id)

    agent_response = await AgentResponse.from_agent(latest_agent, agent_data)
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@team_agent_router.put(
    "/teams/{team_id}/agents/{agent_id}/archive",
    tags=["Team Agent"],
    status_code=204,
    operation_id="team_archive_agent",
    summary="Archive Agent (Team)",
)
async def archive_agent(
    agent_id: str = Path(..., description="Agent ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Archive an agent within the team."""
    _user_id, team_id = auth
    agent = await get_team_agent(agent_id, team_id)

    async with get_session() as db:
        result = await db.execute(select(AgentTable).where(AgentTable.id == agent.id))
        agent_row = result.scalar_one_or_none()
        if agent_row:
            agent_row.archived_at = datetime.now(UTC)
        await db.commit()

    invalidate_lead_cache(team_id)
    return Response(status_code=204)


@team_agent_router.put(
    "/teams/{team_id}/agents/{agent_id}/reactivate",
    tags=["Team Agent"],
    status_code=204,
    operation_id="team_reactivate_agent",
    summary="Reactivate Agent (Team)",
)
async def reactivate_agent(
    agent_id: str = Path(..., description="Agent ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Reactivate an archived agent within the team."""
    _user_id, team_id = auth
    agent = await get_team_agent(agent_id, team_id)

    async with get_session() as db:
        result = await db.execute(select(AgentTable).where(AgentTable.id == agent.id))
        agent_row = result.scalar_one_or_none()
        if agent_row:
            agent_row.archived_at = None
        await db.commit()

    invalidate_lead_cache(team_id)
    return Response(status_code=204)


@team_agent_router.put(
    "/teams/{team_id}/agents/{agent_id}/twitter/unlink",
    tags=["Team OAuth"],
    operation_id="team_unlink_twitter",
    summary="Unlink Twitter (Team)",
)
async def unlink_twitter_endpoint(
    agent_id: str = Path(..., description="Agent ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Unlink Twitter/X from an agent within the team."""
    _user_id, team_id = auth
    agent = await get_team_agent(agent_id, team_id)
    agent_data = await unlink_twitter(agent.id)
    agent_response = await AgentResponse.from_agent(agent, agent_data)
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )
