from unittest.mock import AsyncMock, patch

import pytest

from intentkit.core.chat import clear_thread_memory
from intentkit.utils.error import IntentKitAPIError


@pytest.mark.asyncio
async def test_clear_thread_memory_success():
    """Test successful clearing of thread memory."""
    agent_id = "test_agent"
    chat_id = "test_chat"
    thread_id = f"{agent_id}-{chat_id}"

    # Mock the database session
    mock_session = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None

    with patch("intentkit.core.chat.get_session", return_value=mock_session_ctx):
        result = await clear_thread_memory(agent_id, chat_id)

        assert result is True

        # Verify that execute was called 3 times (one for each table)
        assert mock_session.execute.call_count == 3

        # Check the calls
        calls = mock_session.execute.call_args_list

        # We can inspect the SQL text in the calls
        # The exact order matters if we wrote it sequentially

        # 1. checkpoints
        call1 = calls[0]
        sql1 = call1[0][0]
        params1 = call1[0][1]
        assert "DELETE FROM checkpoints" in str(sql1)
        assert params1 == {"thread_id": thread_id}

        # 2. checkpoint_writes
        call2 = calls[1]
        sql2 = call2[0][0]
        params2 = call2[0][1]
        assert "DELETE FROM checkpoint_writes" in str(sql2)
        assert params2 == {"thread_id": thread_id}

        # 3. checkpoint_blobs
        call3 = calls[2]
        sql3 = call3[0][0]
        params3 = call3[0][1]
        assert "DELETE FROM checkpoint_blobs" in str(sql3)
        assert params3 == {"thread_id": thread_id}

        # Verify commit was called
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_clear_thread_memory_failure():
    """Test failure handling when clearing thread memory."""
    agent_id = "test_agent"
    chat_id = "test_chat"

    # Mock the database session to raise an exception
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.side_effect = Exception("Database connection failed")

    with patch("intentkit.core.chat.get_session", return_value=mock_session_ctx):
        with pytest.raises(IntentKitAPIError) as excinfo:
            await clear_thread_memory(agent_id, chat_id)

        assert excinfo.value.status_code == 500
        assert "Failed to clear thread memory" in str(excinfo.value)
