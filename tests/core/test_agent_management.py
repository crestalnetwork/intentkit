"""Tests for intentkit/core/agent/management.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.utils.error import IntentKitAPIError

MODULE = "intentkit.core.agent.management"


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
        purpose="some purpose",
        wallet_provider="privy",
        weekly_spending_limit=100,
        team_id=None,
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
        "autonomous": None,
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
    agent.autonomous = dump.get("autonomous")
    agent.validate_autonomous_schedule = MagicMock()
    agent.normalize_autonomous_statuses = MagicMock(side_effect=lambda x: x)
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

        mock_get.return_value = MagicMock(purpose="do stuff")
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

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_agent_by_id_or_slug", new_callable=AsyncMock)
    async def test_sub_agent_no_purpose(self, mock_get):
        from intentkit.core.agent.management import _validate_sub_agents

        mock_get.return_value = MagicMock(purpose=None)
        with pytest.raises(IntentKitAPIError) as exc_info:
            await _validate_sub_agents(["no-purpose-agent"])
        assert exc_info.value.status_code == 400
        assert exc_info.value.key == "InvalidSubAgent"
        assert "purpose" in exc_info.value.message


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
    @patch(f"{MODULE}.process_agent_wallet", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    @patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
    async def test_successful_override(
        self, mock_get_agent, mock_get_session, mock_wallet, mock_notify
    ):
        from intentkit.core.agent.management import override_agent

        existing = _make_existing_agent()
        mock_get_agent.return_value = existing

        session_ctx, mock_session = _make_session_mock()
        mock_get_session.return_value = session_ctx

        db_agent = MagicMock()
        mock_session.get = AsyncMock(return_value=db_agent)
        mock_session.scalar = AsyncMock(return_value=None)  # slug unique check

        agent_data = MagicMock()
        mock_wallet.return_value = agent_data

        agent_update = _make_agent_update(slug="my-slug")

        with patch("intentkit.models.agent.Agent.model_validate") as mock_validate:
            mock_validate.return_value = _make_existing_agent()
            result_agent, result_data = await override_agent(
                "agent-1", agent_update, "owner-1"
            )

        mock_session.commit.assert_awaited_once()
        mock_wallet.assert_awaited_once()
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
    @patch(f"{MODULE}.process_agent_wallet", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    @patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
    async def test_successful_patch(
        self, mock_get_agent, mock_get_session, mock_wallet, mock_notify
    ):
        from intentkit.core.agent.management import patch_agent

        existing = _make_existing_agent()
        mock_get_agent.return_value = existing

        session_ctx, mock_session = _make_session_mock()
        mock_get_session.return_value = session_ctx

        db_agent = MagicMock()
        mock_session.get = AsyncMock(return_value=db_agent)
        mock_session.scalar = AsyncMock(return_value=None)

        agent_data = MagicMock()
        mock_wallet.return_value = agent_data

        # Only updating slug (same value) via exclude_unset
        agent_update = _make_agent_update(slug="my-slug")

        with patch("intentkit.models.agent.Agent.model_validate") as mock_validate:
            mock_validate.return_value = _make_existing_agent()
            result_agent, result_data = await patch_agent(
                "agent-1", agent_update, "owner-1"
            )

        mock_session.commit.assert_awaited_once()
        mock_wallet.assert_awaited_once()
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
        agent_create.autonomous = None
        agent_create.slug = None

        with patch(f"{MODULE}.AgentTable") as mock_table:
            mock_table.return_value = MagicMock()
            with pytest.raises(IntentKitAPIError) as exc_info:
                await create_agent(agent_create)
        assert exc_info.value.status_code == 400
        assert exc_info.value.key == "AgentExists"

    @pytest.mark.asyncio
    @patch(f"{MODULE}.send_agent_notification")
    @patch(f"{MODULE}.process_agent_wallet", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    async def test_successful_creation(
        self, mock_get_session, mock_wallet, mock_notify
    ):
        from intentkit.core.agent.management import create_agent

        session_ctx, mock_session = _make_session_mock()
        mock_get_session.return_value = session_ctx
        mock_session.scalar = AsyncMock(return_value=None)

        agent_data = MagicMock()
        mock_wallet.return_value = agent_data

        agent_create = _make_agent_create(owner="owner-1")
        agent_create.upstream_id = None
        agent_create.sub_agents = None
        agent_create.autonomous = None
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
        mock_wallet.assert_awaited_once()
        mock_notify.assert_called_once()


# ===========================================================================
# deploy_agent
# ===========================================================================


class TestDeployAgent:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.override_agent", new_callable=AsyncMock)
    async def test_existing_agent_calls_override(self, mock_override):
        from intentkit.core.agent.management import deploy_agent

        expected = (MagicMock(), MagicMock())
        mock_override.return_value = expected

        agent_update = _make_agent_update()
        result = await deploy_agent("agent-1", agent_update, "owner-1")

        mock_override.assert_awaited_once_with("agent-1", agent_update, "owner-1")
        assert result == expected

    @pytest.mark.asyncio
    @patch(f"{MODULE}.create_agent", new_callable=AsyncMock)
    @patch(f"{MODULE}.override_agent", new_callable=AsyncMock)
    async def test_not_found_falls_back_to_create(self, mock_override, mock_create):
        from intentkit.core.agent.management import deploy_agent

        mock_override.side_effect = IntentKitAPIError(404, "AgentNotFound", "not found")
        expected = (MagicMock(), MagicMock())
        mock_create.return_value = expected

        agent_update = _make_agent_update()

        with patch("intentkit.models.agent.AgentCreate.model_validate") as mock_v:
            mock_new = MagicMock()
            mock_v.return_value = mock_new
            result = await deploy_agent("agent-1", agent_update, "owner-1")

        mock_create.assert_awaited_once()
        assert mock_new.id == "agent-1"
        assert mock_new.owner == "owner-1"
        assert result == expected

    @pytest.mark.asyncio
    @patch(f"{MODULE}.override_agent", new_callable=AsyncMock)
    async def test_non_404_error_propagates(self, mock_override):
        from intentkit.core.agent.management import deploy_agent

        mock_override.side_effect = IntentKitAPIError(403, "Forbidden", "forbidden")
        agent_update = _make_agent_update()
        with pytest.raises(IntentKitAPIError) as exc_info:
            await deploy_agent("agent-1", agent_update, "owner-1")
        assert exc_info.value.status_code == 403


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
