# pyright: reportPrivateUsage=false
"""Tests for the unified GET /agents/{agent_id} endpoint visibility logic."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from intentkit.models.agent.core import AgentVisibility

from app.team.agent import _agent_visible_to


def _agent(
    *, visibility: AgentVisibility | None, archived: bool = False, team_id: str = "t1"
) -> MagicMock:
    agent = MagicMock()
    agent.visibility = visibility
    agent.archived_at = datetime.now(UTC) if archived else None
    agent.team_id = team_id
    return agent


class TestAgentVisibleTo:
    @pytest.mark.asyncio
    async def test_public_agent_visible_to_anonymous(self):
        agent = _agent(visibility=AgentVisibility.PUBLIC)
        assert await _agent_visible_to(agent, None) is True

    @pytest.mark.asyncio
    async def test_archived_public_agent_hidden_from_anonymous(self):
        agent = _agent(visibility=AgentVisibility.PUBLIC, archived=True)
        assert await _agent_visible_to(agent, None) is False

    @pytest.mark.asyncio
    async def test_private_agent_hidden_from_anonymous(self):
        agent = _agent(visibility=AgentVisibility.PRIVATE)
        assert await _agent_visible_to(agent, None) is False

    @pytest.mark.asyncio
    async def test_team_agent_hidden_from_anonymous(self):
        agent = _agent(visibility=AgentVisibility.TEAM)
        assert await _agent_visible_to(agent, None) is False

    @pytest.mark.asyncio
    async def test_private_agent_visible_to_team_member(self, monkeypatch):
        agent = _agent(visibility=AgentVisibility.PRIVATE)

        async def fake_check_permission(*_args, **_kwargs):
            return True

        monkeypatch.setattr(
            "app.team.agent.check_permission", fake_check_permission
        )
        assert await _agent_visible_to(agent, "user-1") is True

    @pytest.mark.asyncio
    async def test_private_agent_hidden_from_non_member(self, monkeypatch):
        agent = _agent(visibility=AgentVisibility.PRIVATE)

        async def fake_check_permission(*_args, **_kwargs):
            return False

        monkeypatch.setattr(
            "app.team.agent.check_permission", fake_check_permission
        )
        assert await _agent_visible_to(agent, "user-1") is False

    @pytest.mark.asyncio
    async def test_archived_private_agent_visible_to_team_member(self, monkeypatch):
        agent = _agent(visibility=AgentVisibility.PRIVATE, archived=True)

        async def fake_check_permission(*_args, **_kwargs):
            return True

        monkeypatch.setattr(
            "app.team.agent.check_permission", fake_check_permission
        )
        assert await _agent_visible_to(agent, "user-1") is True

    @pytest.mark.asyncio
    async def test_missing_team_id_blocks_non_public(self):
        agent = _agent(visibility=AgentVisibility.PRIVATE, team_id="")
        assert await _agent_visible_to(agent, "user-1") is False

    @pytest.mark.asyncio
    async def test_none_visibility_treated_as_private(self, monkeypatch):
        agent = _agent(visibility=None)

        async def fake_check_permission(*_args, **_kwargs):
            return False

        monkeypatch.setattr(
            "app.team.agent.check_permission", fake_check_permission
        )
        assert await _agent_visible_to(agent, None) is False
        assert await _agent_visible_to(agent, "user-1") is False
