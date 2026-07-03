# pyright: reportPrivateUsage=false
"""Tests for the team links API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Response

from intentkit.clients.composio import ComposioNotConfiguredError
from intentkit.core.team.link import LinkForbiddenError, LinkStateError
from intentkit.utils.error import IntentKitAPIError

from app.team.link import (
    LinkCompleteRequest,
    complete_link,
    connect_link,
    delete_link,
    list_links,
)

MODULE = "app.team.link"
AUTH = ("user-123", "team-456")


class TestListLinks:
    @pytest.mark.asyncio
    async def test_delegates_to_core(self):
        with patch(f"{MODULE}.list_team_links", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = {"enabled": True, "apps": []}
            result = await list_links(auth=AUTH)
        mock_list.assert_awaited_once_with("team-456")
        assert result == {"enabled": True, "apps": []}


class TestConnectLink:
    @pytest.mark.asyncio
    async def test_returns_redirect_url(self):
        with patch(
            f"{MODULE}.initiate_team_link",
            new_callable=AsyncMock,
            return_value="https://go",
        ) as mock_init:
            result = await connect_link(app="gmail", auth=AUTH)
        mock_init.assert_awaited_once_with("team-456", "gmail", "user-123")
        assert result.url == "https://go"

    @pytest.mark.asyncio
    async def test_unconfigured_maps_to_400(self):
        with patch(
            f"{MODULE}.initiate_team_link",
            new_callable=AsyncMock,
            side_effect=ComposioNotConfiguredError("no key"),
        ):
            with pytest.raises(IntentKitAPIError) as exc:
                await connect_link(app="gmail", auth=AUTH)
        assert exc.value.status_code == 400
        assert exc.value.key == "ComposioNotConfigured"

    @pytest.mark.asyncio
    async def test_unknown_app_maps_to_400(self):
        with patch(
            f"{MODULE}.initiate_team_link",
            new_callable=AsyncMock,
            side_effect=LinkStateError("not whitelisted"),
        ):
            with pytest.raises(IntentKitAPIError) as exc:
                await connect_link(app="facebook", auth=AUTH)
        assert exc.value.status_code == 400
        assert exc.value.key == "InvalidLinkApp"

    @pytest.mark.asyncio
    async def test_upstream_failure_maps_to_502(self):
        with patch(
            f"{MODULE}.initiate_team_link",
            new_callable=AsyncMock,
            side_effect=RuntimeError("composio down"),
        ):
            with pytest.raises(IntentKitAPIError) as exc:
                await connect_link(app="gmail", auth=AUTH)
        assert exc.value.status_code == 502
        assert exc.value.key == "LinkInitiationFailed"


class TestDeleteLink:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        with patch(f"{MODULE}.delete_team_link", new_callable=AsyncMock) as mock_delete:
            response = await delete_link(link_id="link-1", auth=AUTH)
        mock_delete.assert_awaited_once_with("team-456", "link-1")
        assert isinstance(response, Response)
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_missing_maps_to_404(self):
        with patch(
            f"{MODULE}.delete_team_link",
            new_callable=AsyncMock,
            side_effect=LinkStateError("not found"),
        ):
            with pytest.raises(IntentKitAPIError) as exc:
                await delete_link(link_id="link-1", auth=AUTH)
        assert exc.value.status_code == 404
        assert exc.value.key == "LinkNotFound"


class TestCompleteLink:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        link = AsyncMock()
        link.team_id = "team-456"
        link.app = "gmail"
        with patch(
            f"{MODULE}.complete_team_link",
            new_callable=AsyncMock,
            return_value=link,
        ) as mock_complete:
            result = await complete_link(
                body=LinkCompleteRequest(connected_account_id="ca_1"),
                user_id="user-123",
            )
        mock_complete.assert_awaited_once_with("user-123", "ca_1")
        assert result.team_id == "team-456"
        assert result.app == "gmail"

    @pytest.mark.asyncio
    async def test_invalid_state_maps_to_400(self):
        with patch(
            f"{MODULE}.complete_team_link",
            new_callable=AsyncMock,
            side_effect=LinkStateError("unknown attempt"),
        ):
            with pytest.raises(IntentKitAPIError) as exc:
                await complete_link(
                    body=LinkCompleteRequest(connected_account_id="ca_1"),
                    user_id="user-123",
                )
        assert exc.value.status_code == 400
        assert exc.value.key == "InvalidLink"

    @pytest.mark.asyncio
    async def test_forbidden_maps_to_403(self):
        with patch(
            f"{MODULE}.complete_team_link",
            new_callable=AsyncMock,
            side_effect=LinkForbiddenError("not admin"),
        ):
            with pytest.raises(IntentKitAPIError) as exc:
                await complete_link(
                    body=LinkCompleteRequest(connected_account_id="ca_1"),
                    user_id="user-123",
                )
        assert exc.value.status_code == 403
        assert exc.value.key == "NotTeamAdmin"

    @pytest.mark.asyncio
    async def test_unexpected_failure_maps_to_400(self):
        with patch(
            f"{MODULE}.complete_team_link",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(IntentKitAPIError) as exc:
                await complete_link(
                    body=LinkCompleteRequest(connected_account_id="ca_1"),
                    user_id="user-123",
                )
        assert exc.value.status_code == 400
        assert exc.value.key == "LinkFailed"
