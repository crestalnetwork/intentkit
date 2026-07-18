"""Tests for intentkit/core/agent/management.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from intentkit.config.base import Base
from intentkit.models.agent_data import AgentDataTable
from intentkit.utils.error import IntentKitAPIError

MODULE = "intentkit.core.agent.management"


@pytest_asyncio.fixture()
async def agent_data_table(db_engine):
    """Create the agent data table: create/patch/override resolve AgentData
    from the real test DB after persisting."""
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[AgentDataTable.__table__])
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_mock():
    """Create an async context manager mock for get_session()."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
    return mock_session_ctx, mock_session


def _make_existing_agent(**overrides):
    """Return a MagicMock that looks like an Agent returned by get_agent."""
    defaults = dict(
        id="agent-1",
        owner="owner-1",
        slug="my-slug",
        system_prompt="## Purpose\n\nsome purpose",
        team_id=None,
        visibility=None,
        archived_at=None,
        sub_agents=None,
    )
    defaults.update(overrides)
    agent = MagicMock()
    for k, v in defaults.items():
        setattr(agent, k, v)
    return agent


def _make_agent_update(**overrides):
    """Return a MagicMock(spec-ish) for AgentUpdate."""
    agent = MagicMock()
    dump = {
        "slug": "my-slug",
        "sub_agents": None,
        "tools": None,
    }
    dump.update(overrides)
    agent.model_dump = MagicMock(return_value=dict(dump))
    # exclude_unset variant
    agent.model_dump.side_effect = lambda **kw: (
        {k: v for k, v in dump.items() if k in overrides}
        if kw.get("exclude_unset")
        else dict(dump)
    )
    agent.hash = MagicMock(return_value="abc123")
    agent.slug = dump.get("slug")
    agent.sub_agents = dump.get("sub_agents")
    agent.tools = dump.get("tools")
    agent.visibility = dump.get("visibility")
    agent.archived_at = dump.get("archived_at")
    return agent


def _make_agent_create(**overrides):
    """Return a MagicMock for AgentCreate."""
    agent = _make_agent_update(**overrides)
    agent.owner = overrides.get("owner")
    agent.id = overrides.get("id")
    agent.upstream_id = overrides.get("upstream_id")
    return agent


# ===========================================================================
# _validate_slug_unique
# ===========================================================================


class TestValidateSlugUnique:
    @pytest.mark.asyncio
    async def test_slug_is_unique(self):
        from intentkit.core.agent.management import _validate_slug_unique

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=None)
        # Should not raise
        await _validate_slug_unique("new-slug", None, db)

    @pytest.mark.asyncio
    async def test_slug_already_exists(self):
        from intentkit.core.agent.management import _validate_slug_unique

        db = AsyncMock()
        db.scalar = AsyncMock(return_value="existing-id")
        with pytest.raises(IntentKitAPIError) as exc_info:
            await _validate_slug_unique("taken-slug", None, db)
        assert exc_info.value.status_code == 400
        assert exc_info.value.key == "SlugAlreadyExists"

    @pytest.mark.asyncio
    async def test_exclude_self(self):
        from intentkit.core.agent.management import _validate_slug_unique

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=None)
        # Should not raise when excluding own agent id
        await _validate_slug_unique("my-slug", "agent-1", db)


# ===========================================================================
# _validate_sub_agents
# ===========================================================================


class TestValidateSubAgents:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_agent_by_id_or_slug", new_callable=AsyncMock)
    async def test_all_valid(self, mock_get):
        from intentkit.core.agent.management import _validate_sub_agents

        mock_get.return_value = MagicMock()
        await _validate_sub_agents(["sub-1", "sub-2"])
        assert mock_get.call_count == 2

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_agent_by_id_or_slug", new_callable=AsyncMock)
    async def test_sub_agent_not_found(self, mock_get):
        from intentkit.core.agent.management import _validate_sub_agents

        mock_get.return_value = None
        with pytest.raises(IntentKitAPIError) as exc_info:
            await _validate_sub_agents(["missing-agent"])
        assert exc_info.value.status_code == 400
        assert exc_info.value.key == "InvalidSubAgent"
        assert "not found" in exc_info.value.message


# ===========================================================================
# override_agent
# ===========================================================================


class TestOverrideAgent:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
    async def test_agent_not_found(self, mock_get_agent):
        from intentkit.core.agent.management import override_agent

        mock_get_agent.return_value = None
        agent_update = _make_agent_update()
        with pytest.raises(IntentKitAPIError) as exc_info:
            await override_agent("agent-1", agent_update, "owner-1")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
    async def test_wrong_owner(self, mock_get_agent):
        from intentkit.core.agent.management import override_agent

        mock_get_agent.return_value = _make_existing_agent()
        agent_update = _make_agent_update()
        with pytest.raises(IntentKitAPIError) as exc_info:
            await override_agent("agent-1", agent_update, "other-owner")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
    async def test_slug_immutability(self, mock_get_agent):
        from intentkit.core.agent.management import override_agent

        mock_get_agent.return_value = _make_existing_agent(slug="original-slug")
        agent_update = _make_agent_update(slug="different-slug")
        with pytest.raises(IntentKitAPIError) as exc_info:
            await override_agent("agent-1", agent_update, "owner-1")
        assert exc_info.value.status_code == 400
        assert exc_info.value.key == "SlugImmutable"

    @pytest.mark.asyncio
    @patch(f"{MODULE}.send_agent_notification")
    @patch(f"{MODULE}._validate_wallet_tools", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    @patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
    async def test_successful_override(
        self,
        mock_get_agent,
        mock_get_session,
        mock_validate_wallet,
        mock_notify,
        agent_data_table,
    ):
        from intentkit.core.agent.management import override_agent

        existing = _make_existing_agent()
        mock_get_agent.return_value = existing

        session_ctx, mock_session = _make_session_mock()
        mock_get_session.return_value = session_ctx

        db_agent = MagicMock()
        mock_session.get = AsyncMock(return_value=db_agent)
        mock_session.scalar = AsyncMock(return_value=None)  # slug unique check

        mock_validate_wallet.return_value = None  # wallet gating no-op

        agent_update = _make_agent_update(slug="my-slug")

        with patch("intentkit.models.agent.Agent.model_validate") as mock_validate:
            mock_validate.return_value = _make_existing_agent()
            result_agent, result_data = await override_agent(
                "agent-1", agent_update, "owner-1"
            )

        mock_session.commit.assert_awaited_once()
        # Wallet binding is validated before persisting
        mock_validate_wallet.assert_awaited_once_with(
            agent_update.tools, existing.team_id
        )
        mock_notify.assert_called_once()


# ===========================================================================
# patch_agent
# ===========================================================================


class TestPatchAgent:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
    async def test_agent_not_found(self, mock_get_agent):
        from intentkit.core.agent.management import patch_agent

        mock_get_agent.return_value = None
        agent_update = _make_agent_update()
        with pytest.raises(IntentKitAPIError) as exc_info:
            await patch_agent("agent-1", agent_update, "owner-1")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
    async def test_wrong_owner(self, mock_get_agent):
        from intentkit.core.agent.management import patch_agent

        mock_get_agent.return_value = _make_existing_agent()
        agent_update = _make_agent_update()
        with pytest.raises(IntentKitAPIError) as exc_info:
            await patch_agent("agent-1", agent_update, "other-owner")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    @patch(f"{MODULE}.send_agent_notification")
    @patch(f"{MODULE}._validate_wallet_tools", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    @patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
    async def test_successful_patch(
        self,
        mock_get_agent,
        mock_get_session,
        mock_validate_wallet,
        mock_notify,
        agent_data_table,
    ):
        from intentkit.core.agent.management import patch_agent

        existing = _make_existing_agent()
        mock_get_agent.return_value = existing

        session_ctx, mock_session = _make_session_mock()
        mock_get_session.return_value = session_ctx

        db_agent = MagicMock()
        mock_session.get = AsyncMock(return_value=db_agent)
        mock_session.scalar = AsyncMock(return_value=None)

        mock_validate_wallet.return_value = None  # wallet gating no-op

        # Updating slug (same value) and tools via exclude_unset
        agent_update = _make_agent_update(slug="my-slug", tools=["http_get"])

        with patch("intentkit.models.agent.Agent.model_validate") as mock_validate:
            mock_validate.return_value = _make_existing_agent()
            result_agent, result_data = await patch_agent(
                "agent-1", agent_update, "owner-1"
            )

        mock_session.commit.assert_awaited_once()
        # Web3 gating runs when tools are part of the patch
        mock_validate_wallet.assert_awaited_once_with(["http_get"], existing.team_id)
        mock_notify.assert_called_once()


# ===========================================================================
# create_agent
# ===========================================================================


class TestCreateAgent:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    async def test_duplicate_upstream_id(self, mock_get_session):
        from intentkit.core.agent.management import create_agent

        session_ctx, mock_session = _make_session_mock()
        mock_get_session.return_value = session_ctx
        mock_session.scalar = AsyncMock(return_value=MagicMock())  # existing found

        agent_create = _make_agent_create(upstream_id="dup-upstream")
        with pytest.raises(IntentKitAPIError) as exc_info:
            await create_agent(agent_create)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    async def test_integrity_error(self, mock_get_session):
        from sqlalchemy.exc import IntegrityError

        from intentkit.core.agent.management import create_agent

        session_ctx, mock_session = _make_session_mock()
        mock_get_session.return_value = session_ctx
        mock_session.scalar = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock(
            side_effect=IntegrityError("dup", {}, Exception())
        )

        agent_create = _make_agent_create(owner="owner-1")
        agent_create.upstream_id = None
        agent_create.sub_agents = None
        agent_create.slug = None
        # No tools set, so the real wallet gating is a no-op
        agent_create.tools = None

        with patch(f"{MODULE}.AgentTable") as mock_table:
            mock_table.return_value = MagicMock()
            with pytest.raises(IntentKitAPIError) as exc_info:
                await create_agent(agent_create)
        assert exc_info.value.status_code == 400
        assert exc_info.value.key == "AgentExists"

    @pytest.mark.asyncio
    @patch(f"{MODULE}.send_agent_notification")
    @patch(f"{MODULE}._validate_wallet_tools", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    async def test_successful_creation(
        self, mock_get_session, mock_validate_wallet, mock_notify, agent_data_table
    ):
        from intentkit.core.agent.management import create_agent

        session_ctx, mock_session = _make_session_mock()
        mock_get_session.return_value = session_ctx
        mock_session.scalar = AsyncMock(return_value=None)

        mock_validate_wallet.return_value = None  # wallet gating no-op

        agent_create = _make_agent_create(owner="owner-1")
        agent_create.upstream_id = None
        agent_create.sub_agents = None
        agent_create.slug = None

        with (
            patch(f"{MODULE}.AgentTable") as mock_table,
            patch("intentkit.models.agent.Agent.model_validate") as mock_validate,
        ):
            mock_table.return_value = MagicMock()
            validated_agent = _make_existing_agent(team_id="team-1")
            mock_validate.return_value = validated_agent

            with patch(
                "intentkit.core.team.subscription.auto_subscribe_team",
                new_callable=AsyncMock,
            ) as mock_subscribe:
                result_agent, result_data = await create_agent(agent_create)
                mock_subscribe.assert_awaited_once_with("team-1", validated_agent.id)

        mock_session.commit.assert_awaited_once()
        # Wallet binding is validated before persisting
        mock_validate_wallet.assert_awaited_once_with(
            agent_create.tools, agent_create.team_id
        )
        mock_notify.assert_called_once()


# ===========================================================================
# backfill_agent_avatar (runs as BackgroundTask after create/patch/override)
# ===========================================================================


class TestBackfillAgentAvatar:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    async def test_noop_when_agent_missing(self, mock_get_session):
        from intentkit.core.agent.management import backfill_agent_avatar

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        ctx, _ = _make_session_mock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value = ctx

        await backfill_agent_avatar("ghost")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    async def test_noop_when_picture_already_set(self, mock_get_session):
        from intentkit.core.agent.management import backfill_agent_avatar

        row = MagicMock()
        row.picture = "existing.png"
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=row)
        mock_session.execute = AsyncMock()
        ctx, _ = _make_session_mock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value = ctx

        await backfill_agent_avatar("agent-1")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch("intentkit.core.avatar.generate_avatar", new_callable=AsyncMock)
    @patch("intentkit.models.agent.Agent.model_validate")
    @patch(f"{MODULE}.get_session")
    async def test_happy_path_writes_new_picture(
        self, mock_get_session, mock_validate, mock_generate
    ):
        from intentkit.core.agent.management import backfill_agent_avatar

        # Read: agent row with no picture.
        read_session = MagicMock()
        agent_row = MagicMock()
        agent_row.picture = None
        read_session.get = AsyncMock(return_value=agent_row)
        # Write: update DB with new picture.
        write_session = MagicMock()
        write_session.execute = AsyncMock()
        write_session.commit = AsyncMock()

        read_ctx = MagicMock()
        read_ctx.__aenter__ = AsyncMock(return_value=read_session)
        read_ctx.__aexit__ = AsyncMock(return_value=None)
        write_ctx = MagicMock()
        write_ctx.__aenter__ = AsyncMock(return_value=write_session)
        write_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_get_session.side_effect = [read_ctx, write_ctx]

        agent_snapshot = MagicMock()
        mock_validate.return_value = agent_snapshot
        mock_generate.return_value = "avatars/agent-1/abc.png"

        await backfill_agent_avatar("agent-1")

        mock_generate.assert_awaited_once_with("agent-1", agent_snapshot)
        write_session.execute.assert_awaited_once()
        write_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("intentkit.core.avatar.generate_avatar", new_callable=AsyncMock)
    @patch("intentkit.models.agent.Agent.model_validate")
    @patch(f"{MODULE}.get_session")
    async def test_swallows_generate_failure(
        self, mock_get_session, mock_validate, mock_generate
    ):
        from intentkit.core.agent.management import backfill_agent_avatar

        read_session = MagicMock()
        agent_row = MagicMock()
        agent_row.picture = None
        read_session.get = AsyncMock(return_value=agent_row)

        read_ctx = MagicMock()
        read_ctx.__aenter__ = AsyncMock(return_value=read_session)
        read_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_get_session.side_effect = [read_ctx]

        mock_validate.return_value = MagicMock()
        mock_generate.side_effect = RuntimeError("model down")

        # Must not raise (runs in BackgroundTasks, errors would surface to user).
        await backfill_agent_avatar("agent-1")


# ===========================================================================
# _invalidate_lead_for_team + patch/override wiring
# ===========================================================================


class TestLeadCacheInvalidation:
    @pytest.fixture
    def lead_cache_isolation(self):
        """Snapshot and restore the process-global lead cache dicts so seeded
        MagicMock entries never leak into other tests."""
        from intentkit.core.lead import cache

        names = ("lead_executors", "lead_agents", "lead_cached_at")
        snapshot = {name: dict(getattr(cache, name)) for name in names}
        yield cache
        for name in names:
            d = getattr(cache, name)
            d.clear()
            d.update(snapshot[name])

    def test_invalidate_lead_for_team_drops_only_that_team(self, lead_cache_isolation):
        from intentkit.core.agent.management import _invalidate_lead_for_team

        cache = lead_cache_isolation
        team_id = "team-invalidate-xyz"
        key = cache.lead_cache_key(team_id, "user-1")
        cache.lead_executors[key] = MagicMock()
        cache.lead_agents[key] = MagicMock()
        cache.lead_cached_at[key] = MagicMock()
        # The user-agnostic display entry is keyed by the bare team id.
        cache.lead_agents[team_id] = MagicMock()
        cache.lead_cached_at[team_id] = MagicMock()
        # An unrelated team must survive the targeted invalidation.
        other_key = cache.lead_cache_key("other-team", "user-1")
        cache.lead_agents[other_key] = MagicMock()

        _invalidate_lead_for_team(team_id)

        assert key not in cache.lead_executors
        assert key not in cache.lead_agents
        assert key not in cache.lead_cached_at
        assert team_id not in cache.lead_agents
        assert team_id not in cache.lead_cached_at
        assert other_key in cache.lead_agents

    def test_invalidate_lead_for_team_noop_without_team(self):
        import intentkit.core.lead.cache as cache_mod
        from intentkit.core.agent import management

        # Spy on the cache function the helper imports lazily; the guard must
        # short-circuit for a team-less agent and dispatch for a real team.
        with patch.object(cache_mod, "invalidate_lead_cache") as spy:
            management._invalidate_lead_for_team(None)
            spy.assert_not_called()
            management._invalidate_lead_for_team("team-abc")
            spy.assert_called_once_with("team-abc")

    @pytest.mark.asyncio
    @patch(f"{MODULE}._invalidate_lead_for_team")
    @patch(f"{MODULE}.AgentData.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.send_agent_notification")
    @patch(f"{MODULE}.invalidate_agent_info", new_callable=AsyncMock)
    @patch(f"{MODULE}._validate_wallet_tools", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    @patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
    async def test_patch_invalidates_team_lead(
        self,
        mock_get_agent,
        mock_get_session,
        mock_validate_wallet,
        mock_invalidate_info,
        mock_notify,
        mock_agent_data_get,
        mock_invalidate_lead,
    ):
        from intentkit.core.agent.management import patch_agent

        mock_get_agent.return_value = _make_existing_agent(team_id="team-xyz")
        session_ctx, mock_session = _make_session_mock()
        mock_get_session.return_value = session_ctx
        mock_session.get = AsyncMock(return_value=MagicMock())
        mock_session.scalar = AsyncMock(return_value=None)
        mock_validate_wallet.return_value = None

        agent_update = _make_agent_update(slug="my-slug")
        with patch("intentkit.models.agent.Agent.model_validate") as mock_validate:
            mock_validate.return_value = _make_existing_agent(team_id="team-xyz")
            await patch_agent("agent-1", agent_update, "owner-1")

        mock_invalidate_lead.assert_called_once_with("team-xyz")

    @pytest.mark.asyncio
    @patch(f"{MODULE}._invalidate_lead_for_team")
    @patch(f"{MODULE}.AgentData.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.send_agent_notification")
    @patch(f"{MODULE}.invalidate_agent_info", new_callable=AsyncMock)
    @patch(f"{MODULE}._validate_wallet_tools", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    @patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
    async def test_override_invalidates_team_lead(
        self,
        mock_get_agent,
        mock_get_session,
        mock_validate_wallet,
        mock_invalidate_info,
        mock_notify,
        mock_agent_data_get,
        mock_invalidate_lead,
    ):
        from intentkit.core.agent.management import override_agent

        mock_get_agent.return_value = _make_existing_agent(team_id="team-xyz")
        session_ctx, mock_session = _make_session_mock()
        mock_get_session.return_value = session_ctx
        mock_session.get = AsyncMock(return_value=MagicMock())
        mock_session.scalar = AsyncMock(return_value=None)
        mock_validate_wallet.return_value = None

        agent_update = _make_agent_update(slug="my-slug")
        with patch("intentkit.models.agent.Agent.model_validate") as mock_validate:
            mock_validate.return_value = _make_existing_agent(team_id="team-xyz")
            await override_agent("agent-1", agent_update, "owner-1")

        mock_invalidate_lead.assert_called_once_with("team-xyz")
