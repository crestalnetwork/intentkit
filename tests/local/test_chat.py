# pyright: reportPrivateUsage=false, reportPrivateLocalImportUsage=false, reportUnknownParameterType=false, reportMissingParameterType=false

from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from intentkit.models.chat import AuthorType


@pytest.mark.asyncio
async def testshould_schedule_chat_summary_when_third_user_message(monkeypatch):
    import app.local.chat as chat_module

    monkeypatch.setattr(chat_module, "_count_user_messages", AsyncMock(return_value=2))

    should_schedule = await chat_module.should_schedule_chat_summary(
        "agent-1", "chat-1", AuthorType.WEB
    )

    assert should_schedule is True


@pytest.mark.asyncio
async def test_should_not_schedule_chat_summary_for_non_third_message(monkeypatch):
    import app.local.chat as chat_module

    monkeypatch.setattr(chat_module, "_count_user_messages", AsyncMock(return_value=1))

    should_schedule = await chat_module.should_schedule_chat_summary(
        "agent-1", "chat-1", AuthorType.WEB
    )

    assert should_schedule is False


@pytest.mark.asyncio
async def test_should_not_schedule_chat_summary_for_non_web_author(monkeypatch):
    import app.local.chat as chat_module

    count_mock = AsyncMock(return_value=2)
    monkeypatch.setattr(chat_module, "_count_user_messages", count_mock)

    should_schedule = await chat_module.should_schedule_chat_summary(
        "agent-1", "chat-1", AuthorType.API
    )

    assert should_schedule is False
    count_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_message_schedules_background_summary_task(monkeypatch):
    import app.local.chat as chat_module

    mock_chat = MagicMock()
    mock_chat.agent_id = "agent-1"
    mock_chat.summary = "existing summary"
    mock_chat.add_round = AsyncMock()

    monkeypatch.setattr(chat_module, "get_agent", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(chat_module.Chat, "get", AsyncMock(return_value=mock_chat))
    monkeypatch.setattr(
        chat_module, "should_schedule_chat_summary", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(chat_module, "execute_agent", AsyncMock(return_value=[]))
    schedule_mock = MagicMock()
    monkeypatch.setattr(
        chat_module, "schedule_chat_summary_title_update", schedule_mock
    )

    request = chat_module.LocalChatMessageRequest(
        message="hello",
        stream=False,
        attachments=None,
    )
    _ = await chat_module.send_message(request=request, aid="agent-1", chat_id="chat-1")

    schedule_mock.assert_called_once_with("agent-1", "chat-1")


@pytest.mark.asyncio
async def test_update_chat_summary_title_logs_info_when_chat_missing(monkeypatch):
    import app.local.chat as chat_module

    monkeypatch.setattr(chat_module.Chat, "get", AsyncMock(return_value=None))
    generate_mock = AsyncMock(return_value="should-not-run")
    monkeypatch.setattr(chat_module, "_generate_chat_summary_title", generate_mock)
    info_mock = MagicMock()
    monkeypatch.setattr(chat_module.logger, "info", info_mock)

    await chat_module._update_chat_summary_title("agent-1", "chat-1")

    generate_mock.assert_not_awaited()
    info_mock.assert_called_once()


def test_normalize_summary_title_limits_to_40_chars():
    import app.local.chat as chat_module

    title = chat_module._normalize_summary_title(
        "  This title is intentionally longer than forty characters for testing  "
    )

    assert len(title) <= 40


def testshould_summarize_first_message_uses_byte_length():
    import app.local.chat as chat_module

    assert chat_module.should_summarize_first_message("hello") is False
    assert chat_module.should_summarize_first_message("这是超过二十字节") is True


@pytest.mark.asyncio
async def test_create_chat_thread_triggers_summary_with_long_first_message(monkeypatch):
    import app.local.chat as chat_module

    mock_agent = MagicMock()
    mock_chat = MagicMock()
    mock_chat.id = "chat-1"
    mock_full_chat = MagicMock()

    monkeypatch.setattr(chat_module, "get_agent", AsyncMock(return_value=mock_agent))
    monkeypatch.setattr(
        chat_module.ChatCreate, "save", AsyncMock(return_value=mock_chat)
    )
    monkeypatch.setattr(chat_module.Chat, "get", AsyncMock(return_value=mock_full_chat))
    update_mock = AsyncMock()
    monkeypatch.setattr(
        chat_module, "update_chat_summary_from_first_message", update_mock
    )

    request = chat_module.LocalChatCreateRequest(
        first_message="This first message is clearly longer than twenty bytes.",
    )
    _ = await chat_module.create_chat_thread(request=request, aid="agent-1")

    update_mock.assert_awaited_once_with(
        "agent-1",
        ANY,
        "This first message is clearly longer than twenty bytes.",
    )


@pytest.mark.asyncio
async def test_create_chat_thread_skips_summary_with_short_first_message(monkeypatch):
    import app.local.chat as chat_module

    mock_agent = MagicMock()
    mock_chat = MagicMock()
    mock_chat.id = "chat-1"
    mock_full_chat = MagicMock()

    monkeypatch.setattr(chat_module, "get_agent", AsyncMock(return_value=mock_agent))
    monkeypatch.setattr(
        chat_module.ChatCreate, "save", AsyncMock(return_value=mock_chat)
    )
    monkeypatch.setattr(chat_module.Chat, "get", AsyncMock(return_value=mock_full_chat))
    update_mock = AsyncMock()
    monkeypatch.setattr(
        chat_module, "update_chat_summary_from_first_message", update_mock
    )

    request = chat_module.LocalChatCreateRequest(first_message="short msg")
    _ = await chat_module.create_chat_thread(request=request, aid="agent-1")

    update_mock.assert_not_awaited()
