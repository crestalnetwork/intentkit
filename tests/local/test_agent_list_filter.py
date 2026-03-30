"""Tests for agent list filtering by team_id."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent.db import AgentTable


@pytest.fixture
def system_agent():
    """Agent owned by system team (should appear in local list)."""
    return AgentTable(
        id="system-agent-1",
        slug="system-agent",
        name="System Agent",
        owner="system",
        team_id="system",
        model="google/gemini-2.5-flash",
        visibility=AgentVisibility.PRIVATE,
        archived_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.mark.asyncio
async def test_get_agents_filters_by_system_team(system_agent):
    """Local API list agents should filter by team_id='system'."""
    import app.local.agent as agent_module

    mock_session = AsyncMock()

    # Mock scalars().all() for agents
    mock_scalars_agents = MagicMock()
    mock_scalars_agents.all.return_value = [system_agent]

    # Mock scalars() for agent_data (empty)
    mock_scalars_data = MagicMock()
    mock_scalars_data.__iter__ = MagicMock(return_value=iter([]))

    mock_session.scalars.side_effect = [mock_scalars_agents, mock_scalars_data]

    mock_response = MagicMock()
    mock_response.id = "system-agent-1"

    with (
        patch.object(
            agent_module, "render_agent", new_callable=AsyncMock
        ) as mock_render,
        patch(
            "app.local.agent.AgentResponse.from_agent", new_callable=AsyncMock
        ) as mock_from_agent,
    ):
        mock_render.return_value = MagicMock()
        mock_from_agent.return_value = mock_response

        result = await agent_module.get_agents(db=mock_session)

    assert len(result) == 1
    assert result[0].id == "system-agent-1"


@pytest.mark.asyncio
async def test_get_agents_empty_when_no_system_agents():
    """Empty result when no system team agents exist."""
    import app.local.agent as agent_module

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_session.scalars.return_value = mock_scalars

    result = await agent_module.get_agents(db=mock_session)

    assert result == []
