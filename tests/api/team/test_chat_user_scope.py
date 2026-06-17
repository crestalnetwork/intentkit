"""Tests that team agent chat threads are scoped to team + user.

Each team member should only see and act on their own conversations with a
team agent, not those of other members. The lead agent already enforces this;
these tests cover the regular team agent endpoints in ``app.team.chat``.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.utils.error import IntentKitAPIError

from app.common.chat import ChatUpdateRequest
from app.team.chat import (
    delete_chat_thread,
    get_tool_history,
    list_chats,
    list_messages,
    update_chat_thread,
)

TEAM_ID = "team-a"
OWNER_ID = "user-owner"
OTHER_ID = "user-other"


def _make_agent(agent_id: str = "agent-1"):
    agent = MagicMock()
    agent.id = agent_id
    agent.team_id = TEAM_ID
    return agent


def _make_chat(*, agent_id: str = "agent-1", user_id: str = OWNER_ID):
    chat = MagicMock()
    chat.agent_id = agent_id
    chat.user_id = user_id
    chat.update_summary = AsyncMock(return_value=chat)
    chat.delete = AsyncMock()
    return chat


class TestListChats:
    @pytest.mark.asyncio
    @patch("app.team.chat.Chat.get_by_agent_user", new_callable=AsyncMock)
    @patch("app.team.chat.get_accessible_agent", new_callable=AsyncMock)
    async def test_scoped_to_requesting_user(self, mock_agent, mock_get_by_user):
        """The list is fetched for the calling user only, not the whole team."""
        mock_agent.return_value = _make_agent("agent-1")
        sentinel = [MagicMock()]
        mock_get_by_user.return_value = sentinel

        result = await list_chats(aid="agent-1", auth=(OWNER_ID, TEAM_ID))

        assert result is sentinel
        mock_get_by_user.assert_awaited_once_with("agent-1", OWNER_ID)


class TestOwnershipScope:
    @pytest.mark.asyncio
    @patch("app.team.chat.Chat.get", new_callable=AsyncMock)
    @patch("app.team.chat.get_accessible_agent", new_callable=AsyncMock)
    async def test_update_other_users_chat_blocked(self, mock_agent, mock_get):
        mock_agent.return_value = _make_agent("agent-1")
        mock_get.return_value = _make_chat(user_id=OTHER_ID)
        with pytest.raises(IntentKitAPIError) as exc:
            await update_chat_thread(
                request=ChatUpdateRequest(summary="x"),
                aid="agent-1",
                chat_id="chat-1",
                auth=(OWNER_ID, TEAM_ID),
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.team.chat.Chat.get", new_callable=AsyncMock)
    @patch("app.team.chat.get_accessible_agent", new_callable=AsyncMock)
    async def test_update_own_chat_allowed(self, mock_agent, mock_get):
        mock_agent.return_value = _make_agent("agent-1")
        chat = _make_chat(user_id=OWNER_ID)
        mock_get.return_value = chat
        result = await update_chat_thread(
            request=ChatUpdateRequest(summary="new title"),
            aid="agent-1",
            chat_id="chat-1",
            auth=(OWNER_ID, TEAM_ID),
        )
        assert result is chat
        chat.update_summary.assert_awaited_once_with("new title")

    @pytest.mark.asyncio
    @patch("app.team.chat.Chat.get", new_callable=AsyncMock)
    @patch("app.team.chat.get_accessible_agent", new_callable=AsyncMock)
    async def test_delete_other_users_chat_blocked(self, mock_agent, mock_get):
        mock_agent.return_value = _make_agent("agent-1")
        chat = _make_chat(user_id=OTHER_ID)
        mock_get.return_value = chat
        with pytest.raises(IntentKitAPIError) as exc:
            await delete_chat_thread(
                aid="agent-1", chat_id="chat-1", auth=(OWNER_ID, TEAM_ID)
            )
        assert exc.value.status_code == 404
        chat.delete.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.team.chat.Chat.get", new_callable=AsyncMock)
    @patch("app.team.chat.get_accessible_agent", new_callable=AsyncMock)
    async def test_list_messages_other_users_chat_blocked(self, mock_agent, mock_get):
        mock_agent.return_value = _make_agent("agent-1")
        mock_get.return_value = _make_chat(user_id=OTHER_ID)
        with pytest.raises(IntentKitAPIError) as exc:
            await list_messages(
                aid="agent-1",
                chat_id="chat-1",
                db=MagicMock(),
                auth=(OWNER_ID, TEAM_ID),
                cursor=None,
                limit=20,
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.team.chat.get_accessible_agent", new_callable=AsyncMock)
    async def test_tool_history_filters_by_user_not_team(self, mock_agent):
        """Tool history is filtered by the chat owner, not by team membership."""
        mock_agent.return_value = _make_agent("agent-1")
        result = MagicMock()
        result.all.return_value = []
        db = MagicMock()
        db.scalars = AsyncMock(return_value=result)

        out = await get_tool_history(aid="agent-1", db=db, auth=(OWNER_ID, TEAM_ID))

        assert out == []
        stmt = db.scalars.call_args.args[0]
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        # Scoped to the requesting user's own chats ...
        assert "chats.user_id" in sql
        assert OWNER_ID in sql
        # ... and no longer joined against team membership.
        assert "team_members" not in sql
