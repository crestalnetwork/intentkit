"""Public/sub-agent visibility invariants.

A public agent's call_agent surface is reachable by guests, so every one of
its sub-agents must be public too; conversely an agent referenced by a public
agent cannot be hidden or archived while the reference stands. Enforced in
publish/unpublish, patch/override transitions, and both archive endpoints.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio

from intentkit.config.base import Base
from intentkit.config.db import get_session
from intentkit.core.agent.publish import (
    ensure_not_referenced_by_public_agent,
    ensure_sub_agents_public,
)
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent.db import AgentTable
from intentkit.utils.error import IntentKitAPIError


@pytest_asyncio.fixture()
async def agent_tables(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[AgentTable.__table__])
    yield


async def _add_agent(
    agent_id: str,
    *,
    visibility: AgentVisibility = AgentVisibility.TEAM,
    sub_agents: list[str] | None = None,
    slug: str | None = None,
    archived: bool = False,
    name: str | None = None,
) -> None:
    async with get_session() as db:
        db.add(
            AgentTable(
                id=agent_id,
                name=name or agent_id,
                model="gpt-4o",
                owner="user-1",
                team_id="team-1",
                visibility=visibility,
                sub_agents=sub_agents,
                slug=slug,
                archived_at=datetime.now(UTC) if archived else None,
            )
        )
        await db.commit()


class TestEnsureSubAgentsPublic:
    @pytest.mark.asyncio
    async def test_public_sub_agents_pass(self, agent_tables):
        await _add_agent("sub-1", visibility=AgentVisibility.PUBLIC)
        await ensure_sub_agents_public(["sub-1"])  # must not raise

    @pytest.mark.asyncio
    async def test_resolves_by_slug(self, agent_tables):
        await _add_agent("sub-1", visibility=AgentVisibility.PUBLIC, slug="helper")
        await ensure_sub_agents_public(["helper"])  # must not raise

    @pytest.mark.asyncio
    async def test_team_visibility_sub_agent_rejected(self, agent_tables):
        await _add_agent("sub-1", visibility=AgentVisibility.TEAM)
        with pytest.raises(IntentKitAPIError) as exc_info:
            await ensure_sub_agents_public(["sub-1"])
        assert exc_info.value.key == "SubAgentsNotPublic"
        assert "sub-1" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_archived_public_sub_agent_rejected(self, agent_tables):
        await _add_agent("sub-1", visibility=AgentVisibility.PUBLIC, archived=True)
        with pytest.raises(IntentKitAPIError) as exc_info:
            await ensure_sub_agents_public(["sub-1"])
        assert exc_info.value.key == "SubAgentsNotPublic"

    @pytest.mark.asyncio
    async def test_missing_sub_agent_rejected(self, agent_tables):
        with pytest.raises(IntentKitAPIError) as exc_info:
            await ensure_sub_agents_public(["ghost"])
        assert exc_info.value.key == "SubAgentsNotPublic"

    @pytest.mark.asyncio
    async def test_self_reference_excluded(self, agent_tables):
        await ensure_sub_agents_public(["me", "my-slug"], exclude={"me", "my-slug"})

    @pytest.mark.asyncio
    async def test_empty_is_fine(self, agent_tables):
        await ensure_sub_agents_public(None)
        await ensure_sub_agents_public([])


class TestEnsureNotReferenced:
    @pytest.mark.asyncio
    async def test_referenced_by_public_agent_by_id(self, agent_tables):
        await _add_agent(
            "parent",
            visibility=AgentVisibility.PUBLIC,
            sub_agents=["target"],
            name="Parent Agent",
        )
        await _add_agent("target", visibility=AgentVisibility.PUBLIC)
        with pytest.raises(IntentKitAPIError) as exc_info:
            await ensure_not_referenced_by_public_agent("target", None)
        assert exc_info.value.key == "ReferencedByPublicAgent"
        assert "Parent Agent" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_referenced_by_public_agent_by_slug(self, agent_tables):
        await _add_agent(
            "parent", visibility=AgentVisibility.PUBLIC, sub_agents=["helper"]
        )
        await _add_agent("target", visibility=AgentVisibility.PUBLIC, slug="helper")
        with pytest.raises(IntentKitAPIError) as exc_info:
            await ensure_not_referenced_by_public_agent("target", "helper")
        assert exc_info.value.key == "ReferencedByPublicAgent"

    @pytest.mark.asyncio
    async def test_non_public_referencer_ignored(self, agent_tables):
        await _add_agent(
            "parent", visibility=AgentVisibility.TEAM, sub_agents=["target"]
        )
        await ensure_not_referenced_by_public_agent("target", None)  # must not raise

    @pytest.mark.asyncio
    async def test_archived_referencer_ignored(self, agent_tables):
        await _add_agent(
            "parent",
            visibility=AgentVisibility.PUBLIC,
            sub_agents=["target"],
            archived=True,
        )
        await ensure_not_referenced_by_public_agent("target", None)  # must not raise

    @pytest.mark.asyncio
    async def test_unreferenced_agent_passes(self, agent_tables):
        await ensure_not_referenced_by_public_agent("lonely", "lonely-slug")


class TestTransitionGaps:
    """Regression tests for the bypass paths found in review: un-archiving a
    public agent and creating an agent public-at-birth must both re-validate
    that its sub-agents are public."""

    @pytest.mark.asyncio
    async def test_patch_unarchive_public_revalidates_sub_agents(self):
        from unittest.mock import AsyncMock, MagicMock
        from unittest.mock import patch as mock_patch

        from intentkit.core.agent.management import patch_agent
        from intentkit.models.agent.core import AgentVisibility as Vis

        existing = MagicMock()
        existing.id = "agent-1"
        existing.owner = "owner-1"
        existing.slug = "my-slug"
        existing.visibility = Vis.PUBLIC
        existing.archived_at = datetime.now(UTC)
        existing.sub_agents = ["sub-1"]

        update = MagicMock()
        update.model_dump = MagicMock(
            side_effect=lambda **kw: (
                {"archived_at": None}
                if kw.get("exclude_unset")
                else {"archived_at": None}
            )
        )

        with (
            mock_patch(
                "intentkit.core.agent.management.get_agent",
                new=AsyncMock(return_value=existing),
            ),
            mock_patch(
                "intentkit.core.agent.management.ensure_sub_agents_public",
                new=AsyncMock(
                    side_effect=IntentKitAPIError(400, "SubAgentsNotPublic", "nope")
                ),
            ) as mock_ensure,
        ):
            with pytest.raises(IntentKitAPIError) as exc_info:
                await patch_agent("agent-1", update)

        assert exc_info.value.key == "SubAgentsNotPublic"
        mock_ensure.assert_awaited_once_with(["sub-1"], exclude={"agent-1", "my-slug"})

    @pytest.mark.asyncio
    async def test_create_public_agent_validates_sub_agents(self):
        from unittest.mock import AsyncMock, MagicMock
        from unittest.mock import patch as mock_patch

        from intentkit.core.agent.management import create_agent
        from intentkit.models.agent.core import AgentVisibility as Vis

        agent = MagicMock()
        agent.owner = "owner-1"
        agent.upstream_id = None
        agent.sub_agents = ["hidden-agent"]
        agent.visibility = Vis.PUBLIC
        agent.slug = None
        agent.tools = None

        with (
            mock_patch(
                "intentkit.core.agent.management._validate_sub_agents",
                new=AsyncMock(),
            ),
            mock_patch(
                "intentkit.core.agent.management.ensure_sub_agents_public",
                new=AsyncMock(
                    side_effect=IntentKitAPIError(400, "SubAgentsNotPublic", "nope")
                ),
            ) as mock_ensure,
        ):
            with pytest.raises(IntentKitAPIError) as exc_info:
                await create_agent(agent)

        assert exc_info.value.key == "SubAgentsNotPublic"
        mock_ensure.assert_awaited_once_with(["hidden-agent"], exclude=None)

    @pytest.mark.asyncio
    async def test_reactivate_public_agent_revalidates_sub_agents(self):
        from unittest.mock import AsyncMock, MagicMock
        from unittest.mock import patch as mock_patch

        from intentkit.models.agent.core import AgentVisibility as Vis

        from app.team.agent import reactivate_agent

        agent = MagicMock()
        agent.id = "agent-1"
        agent.slug = "my-slug"
        agent.visibility = Vis.PUBLIC
        agent.sub_agents = ["sub-1"]

        with (
            mock_patch(
                "app.team.agent.get_team_agent", new=AsyncMock(return_value=agent)
            ),
            mock_patch(
                "app.team.agent.ensure_sub_agents_public",
                new=AsyncMock(
                    side_effect=IntentKitAPIError(400, "SubAgentsNotPublic", "nope")
                ),
            ) as mock_ensure,
        ):
            with pytest.raises(IntentKitAPIError) as exc_info:
                await reactivate_agent(agent_id="agent-1", auth=("user-1", "team-1"))

        assert exc_info.value.key == "SubAgentsNotPublic"
        mock_ensure.assert_awaited_once_with(["sub-1"], exclude={"agent-1", "my-slug"})
