# pyright: reportPrivateUsage=false
"""Tests for intentkit.core.team.link module."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import intentkit.core.team.link as link_module
from intentkit.clients.composio import ComposioError
from intentkit.core.team.link import (
    LinkForbiddenError,
    LinkStateError,
    _extract_label,
    build_lead_link_tools,
    build_links_section,
    complete_team_link,
    composio_user_id,
    delete_team_link,
    initiate_team_link,
    links_page_url,
    list_team_links,
)
from intentkit.models.team_link import (
    LINK_APPS,
    LINK_CATEGORIES,
    LINK_LEVEL_TEAM,
    LINK_LEVEL_USER,
    LINK_STATUS_ACTIVE,
    LINK_STATUS_PENDING,
    TeamLink,
)

MODULE = "intentkit.core.team.link"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_link(
    link_id="link1",
    team_id="team1",
    app="gmail",
    connected_account_id="ca_123",
    status=LINK_STATUS_ACTIVE,
    account_label=None,
    created_by="user1",
    level=None,
    user_id=None,
) -> TeamLink:
    """Build a link row; level defaults to the app's whitelist level, and
    user-level links default to being owned by their creator."""
    if level is None:
        level = LINK_APPS[app].level
    if level == LINK_LEVEL_USER and user_id is None:
        user_id = created_by
    now = datetime.now(UTC)
    return TeamLink(
        id=link_id,
        team_id=team_id,
        app=app,
        level=level,
        user_id=user_id,
        connected_account_id=connected_account_id,
        status=status,
        account_label=account_label,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def configured():
    with patch(f"{MODULE}.composio_configured", return_value=True):
        yield


# ---------------------------------------------------------------------------
# Whitelist & URLs
# ---------------------------------------------------------------------------


class TestWhitelist:
    def test_whitelisted_apps(self):
        assert set(LINK_APPS) == {
            # user-level
            "gmail",
            "outlook",
            "googlecalendar",
            "linkedin",
            # team-level
            "twitter",
            "supabase",
            "notion",
            "airtable",
            "googledocs",
            "googlesheets",
            "googleslides",
            "googledrive",
            "linear",
            "github",
            "jira",
            "stripe",
        }

    def test_levels(self):
        user_apps = {a for a, d in LINK_APPS.items() if d.level == LINK_LEVEL_USER}
        assert user_apps == {"gmail", "outlook", "googlecalendar", "linkedin"}
        for app_def in LINK_APPS.values():
            assert app_def.level in (LINK_LEVEL_USER, LINK_LEVEL_TEAM)

    def test_defs_are_complete(self):
        for app_def in LINK_APPS.values():
            assert app_def.name
            assert app_def.description
            assert app_def.toolkit
            assert app_def.categories

    def test_categories_is_ordered_union(self):
        assert list(LINK_CATEGORIES) == list(
            dict.fromkeys(c for d in LINK_APPS.values() for c in d.categories)
        )
        for app_def in LINK_APPS.values():
            for category in app_def.categories:
                assert category in LINK_CATEGORIES


class TestUrls:
    def test_composio_user_id(self):
        assert composio_user_id("team1") == "team-team1"

    def test_team_links_page_url(self):
        with patch.object(link_module.config, "app_base_url", "https://x.example/"):
            assert links_page_url("team1") == "https://x.example/t/team1/links"

    def test_local_links_page_url(self):
        with patch.object(link_module.config, "app_base_url", "https://x.example"):
            assert links_page_url("system") == "https://x.example/links"


# ---------------------------------------------------------------------------
# initiate_team_link
# ---------------------------------------------------------------------------


def _initiate_client() -> MagicMock:
    client = MagicMock()
    client.get_or_create_auth_config = AsyncMock(return_value="ac_1")
    client.initiate_link = AsyncMock(
        return_value=MagicMock(connected_account_id="ca_new", redirect_url="https://go")
    )
    client.delete_connected_account = AsyncMock()
    return client


class TestInitiateTeamLink:
    @pytest.mark.asyncio
    async def test_unknown_app_rejected(self):
        with pytest.raises(LinkStateError):
            await initiate_team_link("team1", "facebook", "user1")

    @pytest.mark.asyncio
    async def test_user_level_app_needs_membership_only(self):
        """Any member may link a user-level app for themselves; the link row
        is bound to that user."""
        client = _initiate_client()
        with (
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_check,
            patch.object(
                TeamLink,
                "delete_pending_for_app",
                new_callable=AsyncMock,
                return_value=["ca_stale"],
            ) as mock_del,
            patch.object(TeamLink, "create", new_callable=AsyncMock) as mock_create,
        ):
            url = await initiate_team_link("team1", "gmail", "user1")

        assert url == "https://go"
        from intentkit.models.team import TeamRole

        mock_check.assert_awaited_once_with("team1", "user1", TeamRole.MEMBER)
        client.get_or_create_auth_config.assert_awaited_once_with("gmail")
        client.initiate_link.assert_awaited_once()
        assert client.initiate_link.await_args.args[0] == "team-team1"
        # A user's new attempt only supersedes their own pending rows
        mock_del.assert_awaited_once_with("team1", "gmail", user_id="user1")
        # Superseded half-open accounts get cleaned up at Composio too
        client.delete_connected_account.assert_awaited_once_with("ca_stale")
        mock_create.assert_awaited_once_with(
            "team1", "gmail", "ca_new", "user1", level="user", user_id="user1"
        )

    @pytest.mark.asyncio
    async def test_team_level_app_requires_admin(self):
        with patch(
            f"{MODULE}.check_permission", new_callable=AsyncMock, return_value=False
        ):
            with pytest.raises(LinkForbiddenError):
                await initiate_team_link("team1", "twitter", "user1")

    @pytest.mark.asyncio
    async def test_team_level_happy_path(self):
        client = _initiate_client()
        with (
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch.object(
                TeamLink,
                "delete_pending_for_app",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_del,
            patch.object(TeamLink, "create", new_callable=AsyncMock) as mock_create,
        ):
            url = await initiate_team_link("team1", "twitter", "user1")

        assert url == "https://go"
        mock_del.assert_awaited_once_with("team1", "twitter", user_id=None)
        mock_create.assert_awaited_once_with(
            "team1", "twitter", "ca_new", "user1", level="team", user_id=None
        )

    @pytest.mark.asyncio
    async def test_verify_roles_false_skips_admin_check(self):
        """The local single-user deployment has no roles."""
        client = _initiate_client()
        with (
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch(f"{MODULE}.check_permission", new_callable=AsyncMock) as mock_check,
            patch.object(
                TeamLink,
                "delete_pending_for_app",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(TeamLink, "create", new_callable=AsyncMock),
        ):
            await initiate_team_link("system", "twitter", "system", verify_roles=False)
        mock_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_initiate_failure_evicts_auth_config(self):
        client = MagicMock()
        client.get_or_create_auth_config = AsyncMock(return_value="ac_1")
        client.initiate_link = AsyncMock(side_effect=ComposioError("stale"))
        with (
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(f"{MODULE}.evict_auth_config") as mock_evict,
        ):
            with pytest.raises(ComposioError):
                await initiate_team_link("team1", "gmail", "user1")
        mock_evict.assert_called_once_with("gmail")


# ---------------------------------------------------------------------------
# complete_team_link
# ---------------------------------------------------------------------------


class TestCompleteTeamLink:
    @pytest.mark.asyncio
    async def test_unknown_account_rejected(self):
        with patch.object(
            TeamLink,
            "get_by_connected_account",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with pytest.raises(LinkStateError):
                await complete_team_link("user1", "ca_x")

    @pytest.mark.asyncio
    async def test_already_active_is_idempotent_for_creator(self):
        link = _make_link(status=LINK_STATUS_ACTIVE, created_by="user1")
        with (
            patch.object(
                TeamLink,
                "get_by_connected_account",
                new_callable=AsyncMock,
                return_value=link,
            ),
            patch(f"{MODULE}.get_composio_client") as mock_client,
        ):
            result = await complete_team_link("user1", "ca_123")
        assert result is link
        mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_active_link_not_disclosed_to_other_users(self):
        link = _make_link(status=LINK_STATUS_ACTIVE, created_by="user1")
        with patch.object(
            TeamLink,
            "get_by_connected_account",
            new_callable=AsyncMock,
            return_value=link,
        ):
            with pytest.raises(LinkStateError):
                await complete_team_link("someone-else", "ca_123")

    @pytest.mark.asyncio
    async def test_wrong_user_rejected(self):
        link = _make_link(status=LINK_STATUS_PENDING, created_by="user1")
        with patch.object(
            TeamLink,
            "get_by_connected_account",
            new_callable=AsyncMock,
            return_value=link,
        ):
            with pytest.raises(LinkStateError):
                await complete_team_link("user2", "ca_123")

    @pytest.mark.asyncio
    async def test_team_level_non_admin_rejected(self):
        link = _make_link(app="twitter", status=LINK_STATUS_PENDING, created_by="user1")
        with (
            patch.object(
                TeamLink,
                "get_by_connected_account",
                new_callable=AsyncMock,
                return_value=link,
            ),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=False,
            ) as mock_check,
        ):
            with pytest.raises(LinkForbiddenError):
                await complete_team_link("user1", "ca_123")
        from intentkit.models.team import TeamRole

        mock_check.assert_awaited_once_with("team1", "user1", TeamRole.ADMIN)

    @pytest.mark.asyncio
    async def test_user_level_needs_membership_only(self):
        """User-level completion checks membership, not admin."""
        link = _make_link(status=LINK_STATUS_PENDING, created_by="user1")
        client = MagicMock()
        client.get_connected_account = AsyncMock(return_value={"status": "ACTIVE"})
        with (
            patch.object(
                TeamLink,
                "get_by_connected_account",
                new_callable=AsyncMock,
                return_value=link,
            ),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_check,
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "set_status", new_callable=AsyncMock),
            patch(f"{MODULE}._invalidate_lead_cache"),
        ):
            await complete_team_link("user1", "ca_123")
        from intentkit.models.team import TeamRole

        mock_check.assert_awaited_once_with("team1", "user1", TeamRole.MEMBER)

    @pytest.mark.asyncio
    async def test_user_level_non_member_rejected(self):
        link = _make_link(status=LINK_STATUS_PENDING, created_by="user1")
        with (
            patch.object(
                TeamLink,
                "get_by_connected_account",
                new_callable=AsyncMock,
                return_value=link,
            ),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            with pytest.raises(LinkForbiddenError):
                await complete_team_link("user1", "ca_123")

    @pytest.mark.asyncio
    async def test_active_account_completes(self):
        link = _make_link(status=LINK_STATUS_PENDING, created_by="user1")
        activated = _make_link(status=LINK_STATUS_ACTIVE, account_label="a@b.c")
        client = MagicMock()
        client.get_connected_account = AsyncMock(
            return_value={
                "status": "ACTIVE",
                "state": {"val": {"email": "a@b.c"}},
            }
        )
        with (
            patch.object(
                TeamLink,
                "get_by_connected_account",
                new_callable=AsyncMock,
                return_value=link,
            ),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(
                TeamLink,
                "set_status",
                new_callable=AsyncMock,
                return_value=activated,
            ) as mock_set,
            patch(f"{MODULE}._invalidate_lead_cache") as mock_invalidate,
        ):
            result = await complete_team_link("user1", "ca_123")

        assert result is activated
        mock_set.assert_awaited_once_with(
            "link1", LINK_STATUS_ACTIVE, account_label="a@b.c"
        )
        # gmail is user-level: only the linking user's executor is dropped
        mock_invalidate.assert_called_once_with("team1", "user1")

    @pytest.mark.asyncio
    async def test_failed_account_deletes_row_and_composio_account(self):
        link = _make_link(status=LINK_STATUS_PENDING, created_by="user1")
        client = MagicMock()
        client.get_connected_account = AsyncMock(return_value={"status": "FAILED"})
        client.delete_connected_account = AsyncMock()
        with (
            patch.object(
                TeamLink,
                "get_by_connected_account",
                new_callable=AsyncMock,
                return_value=link,
            ),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "delete", new_callable=AsyncMock) as mock_delete,
        ):
            with pytest.raises(LinkStateError):
                await complete_team_link("user1", "ca_123")
        mock_delete.assert_awaited_once_with("link1")
        client.delete_connected_account.assert_awaited_once_with("ca_123")

    @pytest.mark.asyncio
    async def test_local_skips_role_checks(self):
        link = _make_link(
            team_id="system", status=LINK_STATUS_PENDING, created_by="system"
        )
        client = MagicMock()
        client.get_connected_account = AsyncMock(return_value={"status": "ACTIVE"})
        with (
            patch.object(
                TeamLink,
                "get_by_connected_account",
                new_callable=AsyncMock,
                return_value=link,
            ),
            patch(f"{MODULE}.check_permission", new_callable=AsyncMock) as mock_check,
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "set_status", new_callable=AsyncMock),
            patch(f"{MODULE}._invalidate_lead_cache"),
        ):
            await complete_team_link("system", "ca_123", verify_roles=False)
        mock_check.assert_not_called()


# ---------------------------------------------------------------------------
# delete_team_link
# ---------------------------------------------------------------------------


class TestDeleteTeamLink:
    @pytest.mark.asyncio
    async def test_missing_link_rejected(self):
        with patch.object(TeamLink, "get", new_callable=AsyncMock, return_value=None):
            with pytest.raises(LinkStateError):
                await delete_team_link("team1", "link1", "user1")

    @pytest.mark.asyncio
    async def test_foreign_team_rejected(self):
        link = _make_link(team_id="other-team")
        with patch.object(TeamLink, "get", new_callable=AsyncMock, return_value=link):
            with pytest.raises(LinkStateError):
                await delete_team_link("team1", "link1", "user1")

    @pytest.mark.asyncio
    async def test_admin_deletes_team_level_link(self, configured):
        link = _make_link(app="twitter")
        client = MagicMock()
        client.delete_connected_account = AsyncMock()
        with (
            patch.object(TeamLink, "get", new_callable=AsyncMock, return_value=link),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "delete", new_callable=AsyncMock) as mock_delete,
            patch(f"{MODULE}._invalidate_lead_cache") as mock_invalidate,
        ):
            await delete_team_link("team1", "link1", "admin1")

        client.delete_connected_account.assert_awaited_once_with("ca_123")
        mock_delete.assert_awaited_once_with("link1")
        # Team-level change: every user's executor is dropped
        mock_invalidate.assert_called_once_with("team1", None)

    @pytest.mark.asyncio
    async def test_member_cannot_delete_team_level_link(self):
        link = _make_link(app="twitter")
        with (
            patch.object(TeamLink, "get", new_callable=AsyncMock, return_value=link),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            with pytest.raises(LinkForbiddenError):
                await delete_team_link("team1", "link1", "member1")

    @pytest.mark.asyncio
    async def test_owner_deletes_own_user_level_link(self, configured):
        """The owning user needs no admin role for their own account."""
        link = _make_link(app="gmail", created_by="user1")
        client = MagicMock()
        client.delete_connected_account = AsyncMock()
        with (
            patch.object(TeamLink, "get", new_callable=AsyncMock, return_value=link),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=False,
            ) as mock_check,
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "delete", new_callable=AsyncMock) as mock_delete,
            patch(f"{MODULE}._invalidate_lead_cache"),
        ):
            await delete_team_link("team1", "link1", "user1")
        mock_check.assert_not_called()
        mock_delete.assert_awaited_once_with("link1")

    @pytest.mark.asyncio
    async def test_other_member_cannot_delete_user_level_link(self):
        link = _make_link(app="gmail", created_by="user1")
        with (
            patch.object(TeamLink, "get", new_callable=AsyncMock, return_value=link),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            with pytest.raises(LinkForbiddenError):
                await delete_team_link("team1", "link1", "user2")

    @pytest.mark.asyncio
    async def test_admin_deletes_user_level_link(self, configured):
        link = _make_link(app="gmail", created_by="user1")
        client = MagicMock()
        client.delete_connected_account = AsyncMock()
        with (
            patch.object(TeamLink, "get", new_callable=AsyncMock, return_value=link),
            patch(
                f"{MODULE}.check_permission",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "delete", new_callable=AsyncMock) as mock_delete,
            patch(f"{MODULE}._invalidate_lead_cache"),
        ):
            await delete_team_link("team1", "link1", "admin1")
        mock_delete.assert_awaited_once_with("link1")

    @pytest.mark.asyncio
    async def test_composio_failure_still_deletes_row(self, configured):
        link = _make_link()
        client = MagicMock()
        client.delete_connected_account = AsyncMock(side_effect=ComposioError("gone"))
        with (
            patch.object(TeamLink, "get", new_callable=AsyncMock, return_value=link),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "delete", new_callable=AsyncMock) as mock_delete,
            patch(f"{MODULE}._invalidate_lead_cache"),
        ):
            await delete_team_link("team1", "link1", "user1")
        mock_delete.assert_awaited_once_with("link1")


# ---------------------------------------------------------------------------
# list_team_links (+ status sync)
# ---------------------------------------------------------------------------


class TestListTeamLinks:
    @pytest.mark.asyncio
    async def test_groups_by_app_and_hides_pending(self, configured):
        links = [
            _make_link(link_id="l1", app="gmail", status=LINK_STATUS_ACTIVE),
            _make_link(
                link_id="l2",
                app="gmail",
                connected_account_id="ca_2",
                status=LINK_STATUS_PENDING,
            ),
        ]
        client = MagicMock()
        client.list_connected_accounts = AsyncMock(
            return_value=[{"id": "ca_123", "status": "ACTIVE"}]
        )
        with (
            patch.object(
                TeamLink,
                "list_for_team",
                new_callable=AsyncMock,
                return_value=links,
            ) as mock_list,
            patch(f"{MODULE}.get_composio_client", return_value=client),
        ):
            result = await list_team_links("team1", "user1")

        mock_list.assert_awaited_once_with("team1")
        assert result.enabled is True
        assert result.categories == list(LINK_CATEGORIES)
        by_app = {a.app: a for a in result.apps}
        assert set(by_app) == set(LINK_APPS)
        assert [link.id for link in by_app["gmail"].links] == ["l1"]
        assert by_app["twitter"].links == []
        # Level and categories come from the whitelist
        assert by_app["gmail"].level == LINK_LEVEL_USER
        assert by_app["twitter"].level == LINK_LEVEL_TEAM
        assert by_app["stripe"].categories == ["Finance & Accounting"]

    @pytest.mark.asyncio
    async def test_other_members_user_links_hidden_but_synced(self, configured):
        """The sync covers all of the team's rows, but another member's
        personal account never shows up in the viewer's response."""
        mine = _make_link(link_id="l1", app="gmail", created_by="user1")
        theirs = _make_link(
            link_id="l2",
            app="gmail",
            connected_account_id="ca_2",
            created_by="user2",
            status=LINK_STATUS_ACTIVE,
        )
        team_row = _make_link(link_id="l3", app="twitter", connected_account_id="ca_3")
        client = MagicMock()
        client.list_connected_accounts = AsyncMock(
            return_value=[{"id": "ca_2", "status": "EXPIRED"}]
        )
        with (
            patch.object(
                TeamLink,
                "list_for_team",
                new_callable=AsyncMock,
                return_value=[mine, theirs, team_row],
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "set_statuses", new_callable=AsyncMock) as mock_set,
            patch(f"{MODULE}._invalidate_lead_cache"),
        ):
            result = await list_team_links("team1", "user1")

        # user2's expired account was healed from user1's page view...
        mock_set.assert_awaited_once_with({"l2": "expired"})
        by_app = {a.app: a for a in result.apps}
        # ...but never exposed to user1.
        assert [link.id for link in by_app["gmail"].links] == ["l1"]
        assert [link.id for link in by_app["twitter"].links] == ["l3"]

    @pytest.mark.asyncio
    async def test_status_sync_downgrades_expired(self, configured):
        link = _make_link(status=LINK_STATUS_ACTIVE)
        client = MagicMock()
        client.list_connected_accounts = AsyncMock(
            return_value=[{"id": "ca_123", "status": "EXPIRED"}]
        )
        with (
            patch.object(
                TeamLink,
                "list_for_team",
                new_callable=AsyncMock,
                return_value=[link],
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "set_statuses", new_callable=AsyncMock) as mock_set,
            patch(f"{MODULE}._invalidate_lead_cache") as mock_invalidate,
        ):
            result = await list_team_links("team1", "user1")

        mock_set.assert_awaited_once_with({"link1": "expired"})
        mock_invalidate.assert_called_once_with("team1")
        gmail = next(a for a in result.apps if a.app == "gmail")
        assert gmail.links[0].status == "expired"

    @pytest.mark.asyncio
    async def test_absent_account_not_marked_revoked(self, configured):
        link = _make_link(status=LINK_STATUS_ACTIVE)
        client = MagicMock()
        client.list_connected_accounts = AsyncMock(return_value=[])
        with (
            patch.object(
                TeamLink,
                "list_for_team",
                new_callable=AsyncMock,
                return_value=[link],
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "set_statuses", new_callable=AsyncMock) as mock_set,
        ):
            await list_team_links("team1", "user1")
        mock_set.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pending_self_heals_when_active_at_composio(self, configured):
        """OAuth finished but the callback never reached us: the sync
        activates the stuck-pending row."""
        pending = _make_link(status=LINK_STATUS_PENDING)
        activated = _make_link(status=LINK_STATUS_ACTIVE, account_label="a@b.c")
        client = MagicMock()
        client.list_connected_accounts = AsyncMock(
            return_value=[
                {
                    "id": "ca_123",
                    "status": "ACTIVE",
                    "state": {"val": {"email": "a@b.c"}},
                }
            ]
        )
        with (
            patch.object(
                TeamLink,
                "list_for_team",
                new_callable=AsyncMock,
                return_value=[pending],
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(
                TeamLink,
                "set_status",
                new_callable=AsyncMock,
                return_value=activated,
            ) as mock_set,
            patch(f"{MODULE}._invalidate_lead_cache") as mock_invalidate,
        ):
            result = await list_team_links("team1", "user1")

        mock_set.assert_awaited_once_with(
            "link1", LINK_STATUS_ACTIVE, account_label="a@b.c"
        )
        mock_invalidate.assert_called_once_with("team1")
        gmail = next(a for a in result.apps if a.app == "gmail")
        assert [link.status for link in gmail.links] == [LINK_STATUS_ACTIVE]

    @pytest.mark.asyncio
    async def test_stuck_pending_cleaned_up_when_dead_at_composio(self, configured):
        pending = _make_link(status=LINK_STATUS_PENDING)
        client = MagicMock()
        client.list_connected_accounts = AsyncMock(
            return_value=[{"id": "ca_123", "status": "EXPIRED"}]
        )
        with (
            patch.object(
                TeamLink,
                "list_for_team",
                new_callable=AsyncMock,
                return_value=[pending],
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "delete", new_callable=AsyncMock) as mock_delete,
        ):
            result = await list_team_links("team1", "user1")

        mock_delete.assert_awaited_once_with("link1")
        gmail = next(a for a in result.apps if a.app == "gmail")
        assert gmail.links == []

    @pytest.mark.asyncio
    async def test_sync_failure_tolerated(self, configured):
        link = _make_link(status=LINK_STATUS_ACTIVE)
        client = MagicMock()
        client.list_connected_accounts = AsyncMock(side_effect=ComposioError("down"))
        with (
            patch.object(
                TeamLink,
                "list_for_team",
                new_callable=AsyncMock,
                return_value=[link],
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
        ):
            result = await list_team_links("team1", "user1")
        gmail = next(a for a in result.apps if a.app == "gmail")
        assert gmail.links[0].status == LINK_STATUS_ACTIVE

    @pytest.mark.asyncio
    async def test_unconfigured_deployment(self):
        with (
            patch(f"{MODULE}.composio_configured", return_value=False),
            patch.object(
                TeamLink, "list_for_team", new_callable=AsyncMock, return_value=[]
            ),
        ):
            result = await list_team_links("team1", "user1")
        assert result.enabled is False
        assert len(result.apps) == len(LINK_APPS)


# ---------------------------------------------------------------------------
# build_lead_link_tools
# ---------------------------------------------------------------------------


class TestBuildLeadLinkTools:
    @pytest.mark.asyncio
    async def test_unconfigured_returns_empty(self):
        with patch(f"{MODULE}.composio_configured", return_value=False):
            assert await build_lead_link_tools("team1", "user1") == []

    @pytest.mark.asyncio
    async def test_no_active_links_returns_empty(self, configured):
        with patch.object(
            TeamLink, "list_visible", new_callable=AsyncMock, return_value=[]
        ):
            assert await build_lead_link_tools("team1", "user1") == []

    @pytest.mark.asyncio
    async def test_happy_path_pins_accounts(self, configured):
        """Team-level and the user's own user-level accounts get pinned."""
        links = [
            _make_link(link_id="l1", app="gmail", connected_account_id="ca_1"),
            _make_link(link_id="l2", app="gmail", connected_account_id="ca_2"),
            _make_link(link_id="l3", app="notion", connected_account_id="ca_3"),
        ]
        client = MagicMock()
        client.create_session = AsyncMock(
            return_value=MagicMock(session_id="s1", mcp_url="https://mcp")
        )
        fake_tools = [MagicMock(), MagicMock()]
        with (
            patch.object(
                TeamLink,
                "list_visible",
                new_callable=AsyncMock,
                return_value=links,
            ) as mock_list,
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch(
                "intentkit.tools.mcp.composio.build_composio_mcp_tools",
                new_callable=AsyncMock,
                return_value=fake_tools,
            ) as mock_build,
        ):
            tools = await build_lead_link_tools("team1", "user1")

        assert tools == fake_tools
        mock_list.assert_awaited_once_with("team1", "user1", status=LINK_STATUS_ACTIVE)
        client.create_session.assert_awaited_once_with(
            "team-team1",
            ["gmail", "notion"],
            {"gmail": ["ca_1", "ca_2"], "notion": ["ca_3"]},
        )
        mock_build.assert_awaited_once_with("https://mcp")

    @pytest.mark.asyncio
    async def test_composio_failure_returns_empty(self, configured):
        links = [_make_link()]
        client = MagicMock()
        client.create_session = AsyncMock(side_effect=ComposioError("down"))
        with (
            patch.object(
                TeamLink,
                "list_visible",
                new_callable=AsyncMock,
                return_value=links,
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
        ):
            assert await build_lead_link_tools("team1", "user1") == []


# ---------------------------------------------------------------------------
# build_links_section
# ---------------------------------------------------------------------------


class TestBuildLinksSection:
    def test_unconfigured_returns_empty(self):
        with patch(f"{MODULE}.composio_configured", return_value=False):
            assert build_links_section("team1", []) == ""

    def test_no_links_yet(self, configured):
        with patch.object(link_module.config, "app_base_url", "https://x.example"):
            section = build_links_section("team1", [])
        assert section.startswith("### Links")
        assert "https://x.example/t/team1/links" in section
        assert section.rstrip().endswith("- (none yet)")
        for app_def in LINK_APPS.values():
            assert app_def.name in section
        # Both levels are explained
        assert "Team-level apps" in section
        assert "User-level apps" in section

    def test_lists_linked_accounts_at_end(self, configured):
        links = [
            _make_link(app="gmail", account_label="a@b.c"),
            _make_link(
                link_id="l2",
                app="twitter",
                connected_account_id="ca_2",
                account_label="@handle",
            ),
            _make_link(
                link_id="l3",
                app="notion",
                connected_account_id="ca_3",
                status="expired",
                account_label="dead",
            ),
        ]
        section = build_links_section("team1", links)
        assert "Accounts linked in this conversation:" in section
        # User-level accounts are marked as the current user's own
        assert "- Gmail (current user's account): a@b.c" in section
        assert "- Twitter / X (team account): @handle" in section
        # Non-active links are not presented as linked accounts
        assert "dead" not in section
        # The account list is the last part of the section
        assert section.rstrip().endswith("- Twitter / X (team account): @handle")


# ---------------------------------------------------------------------------
# _extract_label
# ---------------------------------------------------------------------------


class TestExtractLabel:
    def test_prefers_email(self):
        account: dict[str, object] = {
            "state": {"val": {"email": "a@b.c", "username": "u"}},
            "word_id": "gmail_x",
        }
        assert _extract_label(account) == "a@b.c"

    def test_falls_back_to_word_id(self):
        account: dict[str, object] = {
            "state": {"val": {"access_token": "secret"}},
            "word_id": "tw_x",
        }
        assert _extract_label(account) == "tw_x"

    def test_handles_missing_state(self):
        assert _extract_label({}) is None
