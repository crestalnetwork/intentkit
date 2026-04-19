"""Tests for the team share-link endpoint."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from intentkit.models.share_link import ShareLink, ShareLinkTargetType
from intentkit.utils.error import IntentKitAPIError

from app.team.share import (
    ShareLinkRequest,
    ShareLinkResponse,
    create_team_share_link,
)


def _make_share_link(link_id: str = "sl-xyz") -> ShareLink:
    now = datetime.now(UTC)
    return ShareLink(
        id=link_id,
        target_type=ShareLinkTargetType.POST,
        target_id="post-1",
        agent_id="agent-1",
        user_id=None,
        team_id=None,
        view_count=0,
        created_at=now,
        expires_at=now + timedelta(days=3),
    )


class TestCreateTeamShareLink:
    @pytest.mark.asyncio
    @patch("app.team.share.create_share_link", new_callable=AsyncMock)
    @patch("app.team.share.get_accessible_agent", new_callable=AsyncMock)
    @patch("app.team.share.get_agent_post", new_callable=AsyncMock)
    async def test_creates_post_share(
        self, mock_get_post, mock_accessible, mock_create
    ):
        from unittest.mock import MagicMock

        post = MagicMock()
        post.agent_id = "agent-1"
        mock_get_post.return_value = post
        mock_accessible.return_value = MagicMock()
        mock_create.return_value = _make_share_link("sl-abc")

        payload = ShareLinkRequest(
            target_type=ShareLinkTargetType.POST, target_id="post-1"
        )
        resp = await create_team_share_link(payload, auth=("user-1", "team-1"))

        assert isinstance(resp, ShareLinkResponse)
        assert resp.id == "sl-abc"
        assert resp.target_type == ShareLinkTargetType.POST
        assert "/share/sl-abc" in resp.url
        mock_accessible.assert_awaited_once_with("agent-1", "team-1")
        mock_create.assert_awaited_once()
        call = mock_create.await_args
        assert call.kwargs["user_id"] == "user-1"
        assert call.kwargs["team_id"] == "team-1"

    @pytest.mark.asyncio
    @patch("app.team.share.get_agent_post", new_callable=AsyncMock)
    async def test_404_when_post_missing(self, mock_get_post):
        mock_get_post.return_value = None
        payload = ShareLinkRequest(
            target_type=ShareLinkTargetType.POST, target_id="missing"
        )
        with pytest.raises(IntentKitAPIError) as exc:
            await create_team_share_link(payload, auth=("user-1", "team-1"))
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.team.share.create_share_link", new_callable=AsyncMock)
    @patch("app.team.share.check_permission", new_callable=AsyncMock)
    @patch("app.team.share.get_accessible_agent", new_callable=AsyncMock)
    @patch("app.team.share.Chat")
    async def test_creates_chat_share(
        self, mock_chat_cls, mock_accessible, mock_check, mock_create
    ):
        from unittest.mock import MagicMock

        chat = MagicMock()
        chat.agent_id = "agent-1"
        chat.user_id = "user-2"
        mock_chat_cls.get = AsyncMock(return_value=chat)
        mock_accessible.return_value = MagicMock()
        mock_check.return_value = True
        mock_create.return_value = _make_share_link("sl-chat")

        payload = ShareLinkRequest(
            target_type=ShareLinkTargetType.CHAT, target_id="chat-1"
        )
        resp = await create_team_share_link(payload, auth=("user-1", "team-1"))

        assert resp.id == "sl-chat"
        mock_check.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.team.share.check_permission", new_callable=AsyncMock)
    @patch("app.team.share.get_accessible_agent", new_callable=AsyncMock)
    @patch("app.team.share.Chat")
    async def test_404_when_chat_owner_not_in_team(
        self, mock_chat_cls, mock_accessible, mock_check
    ):
        from unittest.mock import MagicMock

        chat = MagicMock()
        chat.agent_id = "agent-1"
        chat.user_id = "user-outsider"
        mock_chat_cls.get = AsyncMock(return_value=chat)
        mock_accessible.return_value = MagicMock()
        mock_check.return_value = False

        payload = ShareLinkRequest(
            target_type=ShareLinkTargetType.CHAT, target_id="chat-1"
        )
        with pytest.raises(IntentKitAPIError) as exc:
            await create_team_share_link(payload, auth=("user-1", "team-1"))
        assert exc.value.status_code == 404
