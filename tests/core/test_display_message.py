"""Tests for the ``display_message`` tool-call status line.

``ToolBindingMiddleware`` advertises a required ``display_message`` string
argument on every bound tool schema, strips it again before the real tool
executes, and ``handle_tools_chunk`` lifts it out of the recorded call args
into ``ChatMessageToolCall.display_message`` for the UI.
"""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_core.tools.base import ArgsSchema
from langgraph.prebuilt.tool_node import ToolCallRequest
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
from intentkit.core.engine.chunks import handle_tools_chunk
from intentkit.core.middleware import ToolBindingMiddleware
from intentkit.models.chat import (
    DISPLAY_MESSAGE_ARG,
    AuthorType,
    ChatMessage,
    ChatMessageCreate,
)

# ──────────────────────────────────────────────
# Test tools
# ──────────────────────────────────────────────


class _EchoArgs(BaseModel):
    text: str = Field(description="Text to echo")


class _EchoTool(BaseTool):
    name: str = "echo_tool"
    description: str = "Echoes the given text"
    args_schema: ArgsSchema | None = _EchoArgs

    def _run(self, text: str) -> str:
        return text


_DICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"q": {"type": "string", "description": "query"}},
    "required": ["q"],
}


class _DictSchemaTool(BaseTool):
    """MCP-style tool whose args schema is a raw JSON schema dict."""

    name: str = "dict_tool"
    description: str = "Tool with a dict args schema"
    args_schema: ArgsSchema | None = _DICT_SCHEMA

    def _run(self, q: str) -> str:
        return q


class _ConflictArgs(BaseModel):
    display_message: str = Field(description="This tool owns this arg name")


class _ConflictTool(BaseTool):
    name: str = "conflict_tool"
    description: str = "Tool that already defines display_message"
    args_schema: ArgsSchema | None = _ConflictArgs

    def _run(self, display_message: str) -> str:
        return display_message


def _make_middleware(
    tools: list[BaseTool | dict[str, Any]],
) -> ToolBindingMiddleware:
    llm_model = MagicMock()
    llm_model.create_instance = AsyncMock(return_value=MagicMock())
    return ToolBindingMiddleware(llm_model, tools)


def _make_context() -> AgentContext:
    return AgentContext(
        agent_id="agent-1",
        get_agent=lambda: MagicMock(),
        chat_id="chat-1",
        user_id="user-1",
        entrypoint=AuthorType.WEB,
        is_own_team=True,
        call_depth=0,
    )


class _FakeRequest:
    """Minimal stand-in for ModelRequest: runtime.context plus override()."""

    def __init__(self, context: AgentContext) -> None:
        self.runtime = SimpleNamespace(context=context)
        self.overridden: dict[str, Any] = {}

    def override(self, **kwargs: Any) -> "_FakeRequest":
        self.overridden.update(kwargs)
        return self


async def _bound_tools(
    middleware: ToolBindingMiddleware,
) -> dict[str, BaseTool | dict[str, Any]]:
    request = _FakeRequest(_make_context())
    handler = AsyncMock(return_value="response")
    await middleware.awrap_model_call(cast(Any, request), handler)
    handler.assert_awaited_once()
    return {
        t.name if isinstance(t, BaseTool) else str(t): t
        for t in request.overridden["tools"]
    }


# ──────────────────────────────────────────────
# Schema augmentation
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bound_schema_advertises_display_message():
    """Bound tool schemas gain a required display_message string argument."""
    middleware = _make_middleware([_EchoTool(), _DictSchemaTool()])
    bound = await _bound_tools(middleware)

    for name in ("echo_tool", "dict_tool"):
        tool = bound[name]
        assert isinstance(tool, BaseTool)
        schema = tool.tool_call_schema
        assert isinstance(schema, dict)
        prop = schema["properties"][DISPLAY_MESSAGE_ARG]
        assert prop["type"] == "string"
        assert DISPLAY_MESSAGE_ARG in schema["required"]

    # Original arguments survive alongside the injected one.
    echo_schema = cast(
        dict[str, Any], cast(BaseTool, bound["echo_tool"]).tool_call_schema
    )
    assert "text" in echo_schema["properties"]
    assert "text" in echo_schema["required"]
    dict_schema = cast(
        dict[str, Any], cast(BaseTool, bound["dict_tool"]).tool_call_schema
    )
    assert "q" in dict_schema["properties"]


@pytest.mark.asyncio
async def test_stand_in_keeps_name_and_description():
    """The schema stand-in must be indistinguishable by name/description."""
    original = _EchoTool()
    middleware = _make_middleware([original])
    bound = await _bound_tools(middleware)
    stand_in = bound["echo_tool"]
    assert isinstance(stand_in, BaseTool)
    assert stand_in is not original
    assert stand_in.name == original.name
    assert stand_in.description == original.description


def test_original_schemas_not_mutated():
    """Augmentation must never leak into the original tool schemas."""
    dict_tool = _DictSchemaTool()
    _make_middleware([_EchoTool(), dict_tool])

    assert DISPLAY_MESSAGE_ARG not in _DICT_SCHEMA["properties"]
    assert _DICT_SCHEMA["required"] == ["q"]
    assert (
        DISPLAY_MESSAGE_ARG
        not in cast(dict[str, Any], dict_tool.args_schema)["properties"]
    )
    assert DISPLAY_MESSAGE_ARG not in _EchoArgs.model_fields


@pytest.mark.asyncio
async def test_tool_owning_display_message_is_left_alone():
    """A tool that defines display_message itself keeps its original schema."""
    conflict = _ConflictTool()
    middleware = _make_middleware([conflict])
    bound = await _bound_tools(middleware)
    assert bound["conflict_tool"] is conflict


@pytest.mark.asyncio
async def test_dict_server_tools_pass_through():
    """Provider server tools (dict-typed) are bound untouched."""
    server_tool = {"type": "web_search"}
    middleware = _make_middleware([_EchoTool(), server_tool])
    request = _FakeRequest(_make_context())
    await middleware.awrap_model_call(cast(Any, request), AsyncMock())
    assert server_tool in request.overridden["tools"]


# ──────────────────────────────────────────────
# Argument stripping before execution
# ──────────────────────────────────────────────


def _tool_call_request(tool: BaseTool, args: dict[str, Any]) -> ToolCallRequest:
    return ToolCallRequest(
        tool_call={
            "name": tool.name,
            "args": args,
            "id": "call-1",
            "type": "tool_call",
        },
        tool=tool,
        state={},
        runtime=cast(Any, None),
    )


@pytest.mark.asyncio
async def test_display_message_stripped_before_execution():
    tool = _EchoTool()
    middleware = _make_middleware([tool])
    args = {"text": "hi", DISPLAY_MESSAGE_ARG: "Echoing your text"}
    request = _tool_call_request(tool, args)
    handler = AsyncMock(return_value=ToolMessage(content="ok", tool_call_id="call-1"))

    await middleware.awrap_tool_call(request, handler)

    assert handler.await_args is not None
    executed = handler.await_args.args[0]
    assert executed.tool_call["args"] == {"text": "hi"}
    # The original request (and thus the AIMessage tool call) keeps the arg
    # so the engine can persist it for the UI.
    assert request.tool_call["args"] == args


@pytest.mark.asyncio
async def test_no_strip_for_tool_owning_display_message():
    """conflict_tool was never augmented, so its own arg must survive."""
    tool = _ConflictTool()
    middleware = _make_middleware([tool])
    args = {DISPLAY_MESSAGE_ARG: "actual tool input"}
    request = _tool_call_request(tool, args)
    handler = AsyncMock(return_value=ToolMessage(content="ok", tool_call_id="call-1"))

    await middleware.awrap_tool_call(request, handler)

    assert handler.await_args is not None
    assert handler.await_args.args[0].tool_call["args"] == args


# ──────────────────────────────────────────────
# Persistence: lift into ChatMessageToolCall
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chunks_lift_display_message_into_tool_call():
    user_message = ChatMessage(
        id="msg-1",
        agent_id="agent-1",
        chat_id="chat-1",
        user_id="user-1",
        author_id="user-1",
        author_type=AuthorType.WEB,
        message="hi",
        created_at=datetime.now(),
    )
    cached_tool_step = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "echo_tool",
                "args": {"text": "hi", DISPLAY_MESSAGE_ARG: "Echoing your text"},
                "id": "call-1",
                "type": "tool_call",
            },
            {
                "name": "echo_tool",
                "args": {"text": "no status"},
                "id": "call-2",
                "type": "tool_call",
            },
        ],
    )
    chunk = {
        "tools": {
            "messages": [
                ToolMessage(content="ok", tool_call_id="call-1"),
                ToolMessage(content="ok", tool_call_id="call-2"),
            ]
        }
    }
    agent = MagicMock()
    agent.model = "gpt-test"
    model = MagicMock()
    model.calculate_cost = AsyncMock(return_value=Decimal("1"))
    credit_event = MagicMock()
    credit_event.id = "event-1"
    credit_event.total_amount = Decimal("1")

    async def echo_save(self: ChatMessageCreate, session: Any) -> ChatMessageCreate:
        del session
        return self

    with (
        patch("intentkit.core.engine.chunks.get_session") as mock_get_session,
        patch(
            "intentkit.core.engine.chunks.expense_message",
            new_callable=AsyncMock,
            return_value=credit_event,
        ),
        patch(
            "intentkit.core.engine.chunks.expense_tool",
            new_callable=AsyncMock,
            return_value=credit_event,
        ),
        patch(
            "intentkit.core.engine.chunks.get_tool_price",
            return_value=Decimal("1"),
        ),
        patch.object(ChatMessageCreate, "save_in_session", echo_save),
    ):
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

        messages, _last = await handle_tools_chunk(
            chunk,
            user_message,
            agent,
            model,
            payer="team-1",
            this_time=1.0,
            last=0.0,
            thread_id="thread-1",
            cached_tool_step=cached_tool_step,
        )

    tool_calls = messages[0].tool_calls
    assert tool_calls is not None
    first, second = tool_calls
    assert first.get("display_message") == "Echoing your text"
    assert first["parameters"] == {"text": "hi"}
    assert DISPLAY_MESSAGE_ARG not in second
    assert second["parameters"] == {"text": "no status"}


# ──────────────────────────────────────────────
# Pending tool frames (call started / call finished)
# ──────────────────────────────────────────────


def _tool_call_ai_message() -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "echo_tool",
                "args": {"text": "hi", DISPLAY_MESSAGE_ARG: "Echoing your text"},
                "id": "call-1",
                "type": "tool_call",
            },
            {
                "name": "dict_tool",
                "args": {"q": "x"},
                "id": "call-2",
                "type": "tool_call",
            },
        ],
    )


@pytest.mark.asyncio
async def test_pending_frame_yielded_when_tool_calls_start():
    """A model chunk with tool calls yields a transient pending frame."""
    from intentkit.core.engine.chunks import handle_model_chunk

    user_message = ChatMessage(
        id="msg-1",
        agent_id="agent-1",
        chat_id="chat-1",
        user_id="user-1",
        author_id="user-1",
        author_type=AuthorType.WEB,
        message="hi",
        created_at=datetime.now(),
    )
    agent = MagicMock()
    agent.model = "gpt-test"
    chunk = {"model": {"messages": [_tool_call_ai_message()]}}

    messages, _last, cached_tool_step, in_tools_phase = await handle_model_chunk(
        chunk,
        user_message,
        agent,
        MagicMock(),
        payer="team-1",
        this_time=1.0,
        last=0.0,
        thread_id="thread-1",
        cached_tool_step=None,
        in_tools_phase=False,
    )

    assert in_tools_phase is True
    assert cached_tool_step is not None
    assert len(messages) == 1
    frame = messages[0]
    assert frame.pending is True
    assert frame.author_type == AuthorType.TOOL
    assert frame.tool_calls is not None
    first, second = frame.tool_calls
    assert first.get("id") == "call-1"
    assert first.get("display_message") == "Echoing your text"
    assert first["parameters"] == {"text": "hi"}
    assert "success" not in first
    assert second.get("id") == "call-2"
    assert "display_message" not in second


@pytest.mark.asyncio
async def test_execute_agent_skips_pending_frames():
    """Collected (non-streaming) results contain no transient frames."""
    from intentkit.core.engine.stream import execute_agent

    pending = ChatMessage(
        id="frame-1",
        agent_id="agent-1",
        chat_id="chat-1",
        user_id="user-1",
        author_id="agent-1",
        author_type=AuthorType.TOOL,
        message="",
        pending=True,
        created_at=datetime.now(),
    )
    final = ChatMessage(
        id="msg-2",
        agent_id="agent-1",
        chat_id="chat-1",
        user_id="user-1",
        author_id="agent-1",
        author_type=AuthorType.AGENT,
        message="done",
        created_at=datetime.now(),
    )

    async def fake_stream(_message):
        yield pending
        yield final

    with patch("intentkit.core.engine.stream.stream_agent", fake_stream):
        result = await execute_agent(cast(Any, MagicMock()))

    assert result == [final]


def test_pending_field_excluded_from_db_dump():
    """The pending marker must never reach the chat_messages insert."""
    frame = ChatMessage(
        id="frame-1",
        agent_id="agent-1",
        chat_id="chat-1",
        user_id="user-1",
        author_id="agent-1",
        author_type=AuthorType.TOOL,
        message="",
        pending=True,
        created_at=datetime.now(),
    )
    dumped = frame.model_dump(mode="json", exclude={"pending"})
    assert "pending" not in dumped
    # And the wire dump (SSE) does include it for live consumers.
    assert frame.model_dump()["pending"] is True
