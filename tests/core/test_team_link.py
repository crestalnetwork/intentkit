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
) -> TeamLink:
    now = datetime.now(UTC)
    return TeamLink(
        id=link_id,
        team_id=team_id,
        app=app,
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
    def test_first_batch_apps(self):
        assert set(LINK_APPS) == {"twitter", "notion", "gmail"}

    def test_defs_are_complete(self):
        for app_def in LINK_APPS.values():
            assert app_def.name
            assert app_def.description
            assert app_def.toolkit


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


class TestInitiateTeamLink:
    @pytest.mark.asyncio
    async def test_unknown_app_rejected(self):
        with pytest.raises(LinkStateError):
            await initiate_team_link("team1", "facebook", "user1")

    @pytest.mark.asyncio
    async def test_happy_path(self):
        client = MagicMock()
        client.get_or_create_auth_config = AsyncMock(return_value="ac_1")
        client.initiate_link = AsyncMock(
            return_value=MagicMock(
                connected_account_id="ca_new", redirect_url="https://go"
            )
        )
        client.delete_connected_account = AsyncMock()
        with (
            patch(f"{MODULE}.get_composio_client", return_value=client),
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
        client.get_or_create_auth_config.assert_awaited_once_with("gmail")
        client.initiate_link.assert_awaited_once()
        assert client.initiate_link.await_args.args[0] == "team-team1"
        mock_del.assert_awaited_once_with("team1", "gmail")
        # Superseded half-open accounts get cleaned up at Composio too
        client.delete_connected_account.assert_awaited_once_with("ca_stale")
        mock_create.assert_awaited_once_with("team1", "gmail", "ca_new", "user1")

    @pytest.mark.asyncio
    async def test_initiate_failure_evicts_auth_config(self):
        client = MagicMock()
        client.get_or_create_auth_config = AsyncMock(return_value="ac_1")
        client.initiate_link = AsyncMock(side_effect=ComposioError("stale"))
        with (
            patch(f"{MODULE}.get_composio_client", return_value=client),
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
    async def test_non_admin_rejected(self):
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
        mock_invalidate.assert_called_once_with("team1")

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
    async def test_local_skips_admin_check(self):
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
            await complete_team_link("system", "ca_123", verify_admin=False)
        mock_check.assert_not_called()


# ---------------------------------------------------------------------------
# delete_team_link
# ---------------------------------------------------------------------------


class TestDeleteTeamLink:
    @pytest.mark.asyncio
    async def test_missing_link_rejected(self):
        with patch.object(TeamLink, "get", new_callable=AsyncMock, return_value=None):
            with pytest.raises(LinkStateError):
                await delete_team_link("team1", "link1")

    @pytest.mark.asyncio
    async def test_foreign_team_rejected(self):
        link = _make_link(team_id="other-team")
        with patch.object(TeamLink, "get", new_callable=AsyncMock, return_value=link):
            with pytest.raises(LinkStateError):
                await delete_team_link("team1", "link1")

    @pytest.mark.asyncio
    async def test_happy_path(self, configured):
        link = _make_link()
        client = MagicMock()
        client.delete_connected_account = AsyncMock()
        with (
            patch.object(TeamLink, "get", new_callable=AsyncMock, return_value=link),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch.object(TeamLink, "delete", new_callable=AsyncMock) as mock_delete,
            patch(f"{MODULE}._invalidate_lead_cache") as mock_invalidate,
        ):
            await delete_team_link("team1", "link1")

        client.delete_connected_account.assert_awaited_once_with("ca_123")
        mock_delete.assert_awaited_once_with("link1")
        mock_invalidate.assert_called_once_with("team1")

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
            await delete_team_link("team1", "link1")
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
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
        ):
            result = await list_team_links("team1")

        assert result.enabled is True
        by_app = {a.app: a for a in result.apps}
        assert set(by_app) == {"twitter", "notion", "gmail"}
        assert [link.id for link in by_app["gmail"].links] == ["l1"]
        assert by_app["twitter"].links == []

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
            result = await list_team_links("team1")

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
            await list_team_links("team1")
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
            result = await list_team_links("team1")

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
            result = await list_team_links("team1")

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
            result = await list_team_links("team1")
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
            result = await list_team_links("team1")
        assert result.enabled is False
        assert len(result.apps) == len(LINK_APPS)


# ---------------------------------------------------------------------------
# build_lead_link_tools
# ---------------------------------------------------------------------------


class TestBuildLeadLinkTools:
    @pytest.mark.asyncio
    async def test_unconfigured_returns_empty(self):
        with patch(f"{MODULE}.composio_configured", return_value=False):
            assert await build_lead_link_tools("team1") == []

    @pytest.mark.asyncio
    async def test_no_active_links_returns_empty(self, configured):
        with patch.object(
            TeamLink, "list_for_team", new_callable=AsyncMock, return_value=[]
        ):
            assert await build_lead_link_tools("team1") == []

    @pytest.mark.asyncio
    async def test_happy_path_pins_accounts(self, configured):
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
                "list_for_team",
                new_callable=AsyncMock,
                return_value=links,
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
            patch(
                "intentkit.tools.mcp.composio.build_composio_mcp_tools",
                new_callable=AsyncMock,
                return_value=fake_tools,
            ) as mock_build,
        ):
            tools = await build_lead_link_tools("team1")

        assert tools == fake_tools
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
                "list_for_team",
                new_callable=AsyncMock,
                return_value=links,
            ),
            patch(f"{MODULE}.get_composio_client", return_value=client),
        ):
            assert await build_lead_link_tools("team1") == []


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
        assert "Currently linked accounts:" in section
        assert "- Gmail: a@b.c" in section
        assert "- Twitter / X: @handle" in section
        # Non-active links are not presented as linked accounts
        assert "dead" not in section
        # The account list is the last part of the section
        assert section.rstrip().endswith("- Twitter / X: @handle")


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
