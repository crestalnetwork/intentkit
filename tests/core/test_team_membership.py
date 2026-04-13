"""Tests for intentkit.core.team.membership module."""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.models.team import Team, TeamInvite, TeamRole

MODULE = "intentkit.core.team.membership"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session_ctx(mock_session):
    """Return a context-manager mock that yields *mock_session*."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


def _make_team(team_id="my-team", name="My Team", avatar=None):
    now = datetime.now(UTC)
    return Team(id=team_id, name=name, avatar=avatar, created_at=now, updated_at=now)


# ---------------------------------------------------------------------------
# validate_team_id_format  (pure, sync)
# ---------------------------------------------------------------------------


class TestValidateTeamIdFormat:
    validate: Any = None

    def setup_method(self):
        from intentkit.core.team.membership import validate_team_id_format

        self.validate = validate_team_id_format

    def test_too_short(self):
        result = self.validate("ab")
        assert result["valid"] is False
        assert isinstance(result["reason"], str) and "at least 3" in result["reason"]

    def test_too_long(self):
        result = self.validate("a" * 21)
        assert result["valid"] is False
        assert isinstance(result["reason"], str) and "at most 20" in result["reason"]

    def test_uppercase_rejected(self):
        result = self.validate("MyTeam")
        assert result["valid"] is False

    def test_special_chars_rejected(self):
        result = self.validate("my_team!")
        assert result["valid"] is False

    def test_starts_with_digit(self):
        result = self.validate("1team")
        assert result["valid"] is False

    def test_ends_with_hyphen(self):
        result = self.validate("team-")
        assert result["valid"] is False

    def test_valid_short(self):
        assert self.validate("abc")["valid"] is True

    def test_valid_with_hyphens_and_digits(self):
        assert self.validate("my-team-1")["valid"] is True

    def test_valid_max_length(self):
        # 20 chars: starts with letter, ends with digit
        team_id = "a" + "b" * 18 + "1"
        assert len(team_id) == 20
        assert self.validate(team_id)["valid"] is True

    def test_valid_returns_none_reason(self):
        result = self.validate("good-id")
        assert result["reason"] is None


# ---------------------------------------------------------------------------
# validate_team_id  (async)
# ---------------------------------------------------------------------------


class TestValidateTeamId:
    @pytest.mark.asyncio
    async def test_invalid_format_returns_format_error(self):
        from intentkit.core.team.membership import validate_team_id

        result = await validate_team_id("ab")
        assert result["valid"] is False
        assert isinstance(result["reason"], str) and "at least 3" in result["reason"]

    @pytest.mark.asyncio
    @patch(f"{MODULE}.Team.get", new_callable=AsyncMock)
    async def test_already_taken(self, mock_get):
        from intentkit.core.team.membership import validate_team_id

        mock_get.return_value = _make_team()
        result = await validate_team_id("my-team")
        assert result["valid"] is False
        assert isinstance(result["reason"], str) and "already taken" in result["reason"]

    @pytest.mark.asyncio
    @patch(f"{MODULE}.Team.get", new_callable=AsyncMock)
    async def test_available(self, mock_get):
        from intentkit.core.team.membership import validate_team_id

        mock_get.return_value = None
        result = await validate_team_id("new-team")
        assert result["valid"] is True
        assert result["reason"] is None


# ---------------------------------------------------------------------------
# get_team  (async, Redis + DB)
# ---------------------------------------------------------------------------


class TestGetTeam:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.Team.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_redis")
    async def test_cache_hit(self, mock_get_redis, mock_team_get):
        from intentkit.core.team.membership import get_team

        team = _make_team()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=team.model_dump_json())
        mock_get_redis.return_value = mock_redis

        result = await get_team("my-team")
        assert result is not None
        assert result.id == "my-team"
        mock_team_get.assert_not_called()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.Team.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_redis")
    async def test_cache_miss_queries_db_and_caches(
        self, mock_get_redis, mock_team_get
    ):
        from intentkit.core.team.membership import get_team

        team = _make_team()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_team_get.return_value = team

        result = await get_team("my-team")
        assert result is not None
        assert result.id == "my-team"
        mock_team_get.assert_awaited_once_with("my-team")
        mock_redis.set.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.Team.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_redis")
    async def test_cache_miss_team_not_found(self, mock_get_redis, mock_team_get):
        from intentkit.core.team.membership import get_team

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_get_redis.return_value = mock_redis
        mock_team_get.return_value = None

        result = await get_team("missing")
        assert result is None
        mock_redis.set.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.Team.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_redis")
    async def test_redis_error_falls_through_to_db(self, mock_get_redis, mock_team_get):
        from intentkit.core.team.membership import get_team

        team = _make_team()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        mock_redis.set = AsyncMock(side_effect=Exception("Redis down"))
        mock_get_redis.return_value = mock_redis
        mock_team_get.return_value = team

        result = await get_team("my-team")
        assert result is not None
        assert result.id == "my-team"
        mock_team_get.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_team  (async)
# ---------------------------------------------------------------------------


class TestUpdateTeam:
    @pytest.mark.asyncio
    async def test_no_updates_raises(self):
        from intentkit.core.team.membership import update_team

        with pytest.raises(ValueError, match="No updates provided"):
            await update_team("my-team")

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    async def test_team_not_found_raises(self, mock_get_session):
        from intentkit.core.team.membership import update_team

        mock_session = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_cursor)
        mock_get_session.return_value = _mock_session_ctx(mock_session)

        with pytest.raises(ValueError, match="not found"):
            await update_team("missing", name="New Name")

    @pytest.mark.asyncio
    @patch(f"{MODULE}.Team.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_redis")
    @patch(f"{MODULE}.get_session")
    async def test_successful_update_invalidates_cache(
        self, mock_get_session, mock_get_redis, mock_team_get
    ):
        from intentkit.core.team.membership import update_team

        mock_session = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_cursor)
        mock_session.commit = AsyncMock()
        mock_get_session.return_value = _mock_session_ctx(mock_session)

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        updated_team = _make_team(name="Updated Name")
        mock_team_get.return_value = updated_team

        result = await update_team("my-team", name="Updated Name")
        assert result.name == "Updated Name"
        mock_redis.delete.assert_awaited_once()
        mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_invite  (async)
# ---------------------------------------------------------------------------


class TestCreateInvite:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.Team.get", new_callable=AsyncMock)
    async def test_team_not_found_raises(self, mock_team_get):
        from intentkit.core.team.membership import create_invite

        mock_team_get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await create_invite("missing", invited_by="user-1")

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    @patch(f"{MODULE}.Team.get", new_callable=AsyncMock)
    async def test_successful_creation(self, mock_team_get, mock_get_session):
        from intentkit.core.team.membership import create_invite

        mock_team_get.return_value = _make_team()

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # After refresh, the invite table row should look like a valid object
        mock_invite_row = MagicMock()
        mock_invite_row.id = "invite-abc123"
        mock_invite_row.team_id = "my-team"
        mock_invite_row.code = "abc123"
        mock_invite_row.invited_by = "user-1"
        mock_invite_row.role = TeamRole.MEMBER
        mock_invite_row.max_uses = None
        mock_invite_row.use_count = 0
        mock_invite_row.expires_at = None
        mock_invite_row.created_at = datetime.now(UTC)

        async def mock_refresh(instance):
            # Copy attributes to the instance so model_validate works
            for attr in (
                "id",
                "team_id",
                "code",
                "invited_by",
                "role",
                "max_uses",
                "use_count",
                "expires_at",
                "created_at",
            ):
                setattr(instance, attr, getattr(mock_invite_row, attr))

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)
        mock_get_session.return_value = _mock_session_ctx(mock_session)

        result = await create_invite("my-team", invited_by="user-1")
        assert isinstance(result, TeamInvite)
        assert result.team_id == "my-team"
        mock_session.add.assert_called_once()


# ---------------------------------------------------------------------------
# join_team  (async)
# ---------------------------------------------------------------------------


class TestJoinTeam:
    def _setup_session(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_get_session.return_value = _mock_session_ctx(mock_session)
        return mock_session

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    async def test_invalid_code_raises(self, mock_get_session):
        from intentkit.core.team.membership import join_team

        mock_session = self._setup_session(mock_get_session)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Invalid invite code"):
            await join_team("bad-code", "user-1")

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    async def test_expired_invite_raises(self, mock_get_session):
        from intentkit.core.team.membership import join_team

        mock_session = self._setup_session(mock_get_session)
        mock_invite = MagicMock()
        mock_invite.expires_at = datetime.now(UTC) - timedelta(hours=1)
        mock_invite.max_uses = None
        mock_invite.use_count = 0
        mock_invite.team_id = "my-team"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_invite
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="expired"):
            await join_team("expired-code", "user-1")

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    async def test_max_uses_exceeded_raises(self, mock_get_session):
        from intentkit.core.team.membership import join_team

        mock_session = self._setup_session(mock_get_session)
        mock_invite = MagicMock()
        mock_invite.expires_at = None
        mock_invite.max_uses = 5
        mock_invite.use_count = 5
        mock_invite.team_id = "my-team"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_invite
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="maximum uses"):
            await join_team("used-up", "user-1")

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    async def test_already_a_member_raises(self, mock_get_session):
        from intentkit.core.team.membership import join_team

        mock_session = self._setup_session(mock_get_session)
        mock_invite = MagicMock()
        mock_invite.expires_at = None
        mock_invite.max_uses = None
        mock_invite.use_count = 0
        mock_invite.team_id = "my-team"

        # First execute: find invite, second execute: find existing member
        existing_member = MagicMock()
        mock_result_invite = MagicMock()
        mock_result_invite.scalar_one_or_none.return_value = mock_invite

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = existing_member

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_invite, mock_result_member]
        )

        with pytest.raises(ValueError, match="already a member"):
            await join_team("code-123", "user-1")

    @pytest.mark.asyncio
    @patch(f"{MODULE}.Team.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    async def test_successful_join(self, mock_get_session, mock_team_get):
        from intentkit.core.team.membership import join_team

        mock_session = self._setup_session(mock_get_session)
        mock_invite = MagicMock()
        mock_invite.expires_at = None
        mock_invite.max_uses = 10
        mock_invite.use_count = 3
        mock_invite.team_id = "my-team"
        mock_invite.role = TeamRole.MEMBER
        mock_invite.id = 42

        # execute calls: find invite, check member, update use_count
        mock_result_invite = MagicMock()
        mock_result_invite.scalar_one_or_none.return_value = mock_invite

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = None  # not a member

        mock_result_update = MagicMock()

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_invite, mock_result_member, mock_result_update]
        )
        # seats check: scalar returns current member count (0 < seats limit)
        mock_session.scalar = AsyncMock(return_value=0)

        team = _make_team()
        mock_team_get.return_value = team

        result = await join_team("valid-code", "user-1")
        assert result.id == "my-team"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# change_member_role  (async)
# ---------------------------------------------------------------------------


class TestChangeMemberRole:
    @pytest.mark.asyncio
    @patch(f"{MODULE}._invalidate_role_cache", new_callable=AsyncMock)
    @patch(f"{MODULE}._ensure_not_last_owner", new_callable=AsyncMock)
    @patch(f"{MODULE}._get_member_role", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    async def test_demoting_last_owner_raises(
        self, mock_get_session, mock_get_role, mock_ensure, mock_invalidate
    ):
        from intentkit.core.team.membership import change_member_role

        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_get_session.return_value = _mock_session_ctx(mock_session)

        mock_get_role.return_value = TeamRole.OWNER
        mock_ensure.side_effect = ValueError("Cannot remove or demote the last owner")

        with pytest.raises(ValueError, match="last owner"):
            await change_member_role("my-team", "user-1", TeamRole.MEMBER)

    @pytest.mark.asyncio
    @patch(f"{MODULE}._invalidate_role_cache", new_callable=AsyncMock)
    @patch(f"{MODULE}._get_member_role", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    async def test_successful_role_change(
        self, mock_get_session, mock_get_role, mock_invalidate
    ):
        from intentkit.core.team.membership import change_member_role

        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_get_session.return_value = _mock_session_ctx(mock_session)

        mock_get_role.return_value = TeamRole.MEMBER

        await change_member_role("my-team", "user-1", TeamRole.ADMIN)
        mock_session.commit.assert_awaited_once()
        mock_invalidate.assert_awaited_once_with("my-team", "user-1")


# ---------------------------------------------------------------------------
# remove_member  (async)
# ---------------------------------------------------------------------------


class TestRemoveMember:
    @pytest.mark.asyncio
    @patch(f"{MODULE}._invalidate_role_cache", new_callable=AsyncMock)
    @patch(f"{MODULE}._ensure_not_last_owner", new_callable=AsyncMock)
    @patch(f"{MODULE}._get_member_role", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    async def test_removing_last_owner_raises(
        self, mock_get_session, mock_get_role, mock_ensure, mock_invalidate
    ):
        from intentkit.core.team.membership import remove_member

        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_get_session.return_value = _mock_session_ctx(mock_session)

        mock_get_role.return_value = TeamRole.OWNER
        mock_ensure.side_effect = ValueError("Cannot remove or demote the last owner")

        with pytest.raises(ValueError, match="last owner"):
            await remove_member("my-team", "user-1")

    @pytest.mark.asyncio
    @patch(f"{MODULE}._invalidate_role_cache", new_callable=AsyncMock)
    @patch(f"{MODULE}._get_member_role", new_callable=AsyncMock)
    @patch(f"{MODULE}.get_session")
    async def test_successful_removal(
        self, mock_get_session, mock_get_role, mock_invalidate
    ):
        from intentkit.core.team.membership import remove_member

        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_get_session.return_value = _mock_session_ctx(mock_session)

        mock_get_role.return_value = TeamRole.ADMIN

        await remove_member("my-team", "user-1")
        mock_session.commit.assert_awaited_once()
        mock_invalidate.assert_awaited_once_with("my-team", "user-1")


# ---------------------------------------------------------------------------
# check_permission  (async, Redis + DB)
# ---------------------------------------------------------------------------


class TestCheckPermission:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_redis")
    async def test_cache_hit_sufficient_role(self, mock_get_redis):
        from intentkit.core.team.membership import check_permission

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="admin")
        mock_get_redis.return_value = mock_redis

        assert await check_permission("my-team", "user-1", TeamRole.MEMBER) is True

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_redis")
    async def test_cache_hit_insufficient_role(self, mock_get_redis):
        from intentkit.core.team.membership import check_permission

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="member")
        mock_get_redis.return_value = mock_redis

        assert await check_permission("my-team", "user-1", TeamRole.ADMIN) is False

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    @patch(f"{MODULE}.get_redis")
    async def test_cache_miss_not_a_member(self, mock_get_redis, mock_get_session):
        from intentkit.core.team.membership import check_permission

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_get_redis.return_value = mock_redis

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_get_session.return_value = _mock_session_ctx(mock_session)

        assert await check_permission("my-team", "user-1", TeamRole.MEMBER) is False

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_session")
    @patch(f"{MODULE}.get_redis")
    async def test_owner_has_permission_for_member_role(
        self, mock_get_redis, mock_get_session
    ):
        from intentkit.core.team.membership import check_permission

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_get_redis.return_value = mock_redis

        mock_session = MagicMock()
        mock_role = MagicMock()
        mock_role.value = "owner"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_role
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_get_session.return_value = _mock_session_ctx(mock_session)

        assert await check_permission("my-team", "user-1", TeamRole.MEMBER) is True
        # Verify it cached the result
        mock_redis.set.assert_awaited_once()
