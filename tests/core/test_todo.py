"""Tests for the todo system: write_todos tool, TodoMiddleware, snapshotting.

The todo list lives in the graph state's ``todos`` channel, replaced
wholesale by each ``write_todos`` call. The model normally sees the list
through the tool-result echo; summarization destroys those echoes and
snapshots the list into ``todos_snapshot``, which TodoMiddleware re-injects
into the system prompt (refreshed only at compaction time, for prompt-cache
stability).
"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from intentkit.abstracts.graph import AgentContext, Todo
from intentkit.core.middleware import (
    WRITE_TODOS_SYSTEM_PROMPT,
    TodoMiddleware,
)
from intentkit.core.system_tools import write_todos
from intentkit.core.system_tools.write_todos import WriteTodosTool, render_todos
from intentkit.models.chat import AuthorType

# ──────────────────────────────────────────────
# Tool behavior
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_todos_returns_full_replacement_command():
    """The tool writes the whole list to state and echoes a checklist."""
    tool = WriteTodosTool()
    command = await tool._arun(
        todos=[
            {"content": "research", "status": "completed"},
            {"content": "implement", "status": "in_progress"},
            {"content": "test", "status": "pending"},
        ],
        tool_call_id="tc-1",
    )

    update = command.update
    assert update is not None
    update_dict = cast(dict[str, Any], update)
    assert update_dict["todos"] == [
        {"content": "research", "status": "completed"},
        {"content": "implement", "status": "in_progress"},
        {"content": "test", "status": "pending"},
    ]
    (message,) = update_dict["messages"]
    assert isinstance(message, ToolMessage)
    assert message.tool_call_id == "tc-1"
    assert "- [x] research" in str(message.content)
    assert "- [~] implement" in str(message.content)
    assert "- [ ] test" in str(message.content)


@pytest.mark.asyncio
async def test_write_todos_empty_list_clears():
    """An empty list clears the state and says so in the echo."""
    tool = WriteTodosTool()
    command = await tool._arun(todos=[], tool_call_id="tc-2")

    update_dict = cast(dict[str, Any], command.update)
    assert update_dict["todos"] == []
    (message,) = update_dict["messages"]
    assert str(message.content) == "Todo list cleared."


def test_write_todos_markers():
    """Gating flags and the model-facing schema."""
    assert write_todos.name == "write_todos"
    assert write_todos.interactive_only is True
    assert write_todos.context_editing_exempt is True
    # The injected tool_call_id must be hidden from the model.
    schema = convert_to_openai_tool(write_todos)["function"]["parameters"]
    assert list(schema["properties"].keys()) == ["todos"]


def test_render_todos():
    todos: list[Todo] = [
        {"content": "a", "status": "pending"},
        {"content": "b", "status": "in_progress"},
        {"content": "c", "status": "completed"},
    ]
    assert render_todos(todos) == "- [ ] a\n- [~] b\n- [x] c"


# ──────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────
# ToolBindingMiddleware gating of write_todos (interactive_only) is covered
# in test_system_tools_ui.py together with the UI tools; the marker test
# above pins the flag itself.


def _make_context(entrypoint: AuthorType, call_depth: int = 0) -> AgentContext:
    return AgentContext(
        agent_id="agent-1",
        get_agent=lambda: MagicMock(),
        chat_id="chat-1",
        user_id="user-1",
        entrypoint=entrypoint,
        is_own_team=True,
        call_depth=call_depth,
    )


def _runtime(context_kwargs: dict[str, Any] | None = None) -> Any:
    """Runtime stand-in for after-hooks: only ``.context`` is read."""
    kwargs: dict[str, Any] = {"entrypoint": AuthorType.WEB, **(context_kwargs or {})}
    return SimpleNamespace(context=_make_context(**kwargs))


class _FakeRequest:
    """Minimal stand-in for ModelRequest: context, state, system_message,
    plus an ``override()`` that records its kwargs."""

    def __init__(
        self,
        context: AgentContext,
        state: dict[str, Any] | None = None,
        system_message: SystemMessage | None = None,
    ) -> None:
        self.runtime = SimpleNamespace(context=context)
        self.state = state or {}
        self.system_message = system_message
        self.overridden: dict[str, Any] = {}

    def override(self, **kwargs: Any) -> "_FakeRequest":
        self.overridden.update(kwargs)
        return self


# ──────────────────────────────────────────────
# TodoMiddleware: system prompt injection
# ──────────────────────────────────────────────


def _system_text(request: _FakeRequest) -> str:
    message = request.overridden["system_message"]
    return "".join(
        block["text"] for block in message.content_blocks if block["type"] == "text"
    )


@pytest.mark.asyncio
async def test_todo_prompt_appended():
    middleware = TodoMiddleware()
    request = _FakeRequest(
        _make_context(AuthorType.WEB), system_message=SystemMessage("base prompt")
    )
    handler = AsyncMock(return_value="response")

    await middleware.awrap_model_call(cast(Any, request), handler)

    text = _system_text(request)
    assert text.startswith("base prompt")
    assert WRITE_TODOS_SYSTEM_PROMPT in text
    assert "## Current Todo List" not in text  # no snapshot without compaction


@pytest.mark.asyncio
async def test_todo_snapshot_injected_after_compaction():
    middleware = TodoMiddleware()
    snapshot: list[Todo] = [
        {"content": "research", "status": "completed"},
        {"content": "implement", "status": "in_progress"},
    ]
    request = _FakeRequest(
        _make_context(AuthorType.WEB),
        state={"todos_snapshot": snapshot},
        system_message=SystemMessage("base prompt"),
    )
    handler = AsyncMock(return_value="response")

    await middleware.awrap_model_call(cast(Any, request), handler)

    text = _system_text(request)
    assert "## Current Todo List" in text
    assert "- [x] research" in text
    assert "- [~] implement" in text


@pytest.mark.asyncio
async def test_todo_prompt_ignores_live_todos_between_compactions():
    """The live ``todos`` channel never leaks into the prompt — only the
    compaction-time snapshot does, keeping the prompt byte-stable (and thus
    prompt-cacheable) between compactions."""
    middleware = TodoMiddleware()
    request = _FakeRequest(
        _make_context(AuthorType.WEB),
        state={"todos": [{"content": "live item", "status": "pending"}]},
        system_message=SystemMessage("base prompt"),
    )
    handler = AsyncMock(return_value="response")

    await middleware.awrap_model_call(cast(Any, request), handler)

    text = _system_text(request)
    assert "live item" not in text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context_kwargs",
    [
        {"entrypoint": AuthorType.WEB, "call_depth": 1},  # sub-agent run
        {"entrypoint": AuthorType.TRIGGER},  # cron run
    ],
)
async def test_todo_prompt_skipped_without_live_viewer(context_kwargs):
    middleware = TodoMiddleware()
    request = _FakeRequest(
        _make_context(**context_kwargs),
        system_message=SystemMessage("base prompt"),
    )
    handler = AsyncMock(return_value="response")

    await middleware.awrap_model_call(cast(Any, request), handler)

    assert request.overridden == {}  # request passed through untouched
    handler.assert_awaited_once()


# ──────────────────────────────────────────────
# TodoMiddleware: parallel-call guard
# ──────────────────────────────────────────────


def _tool_call(call_id: str, name: str = "write_todos") -> dict[str, Any]:
    return {"name": name, "args": {"todos": []}, "id": call_id, "type": "tool_call"}


@pytest.mark.asyncio
async def test_parallel_write_todos_rejected():
    middleware = TodoMiddleware()
    state = {
        "messages": [
            AIMessage(content="", tool_calls=[_tool_call("a"), _tool_call("b")])
        ]
    }

    result = await middleware.aafter_model(cast(Any, state), _runtime())

    assert result is not None
    errors = result["messages"]
    assert len(errors) == 2
    assert {e.tool_call_id for e in errors} == {"a", "b"}
    assert all(e.status == "error" for e in errors)


@pytest.mark.asyncio
async def test_single_write_todos_allowed():
    middleware = TodoMiddleware()
    state = {"messages": [AIMessage(content="", tool_calls=[_tool_call("a")])]}

    result = await middleware.aafter_model(cast(Any, state), _runtime())

    assert result is None


# ──────────────────────────────────────────────
# TodoMiddleware: task-boundary auto-clear
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_clear_when_all_completed():
    middleware = TodoMiddleware()
    state = {
        "todos": [
            {"content": "a", "status": "completed"},
            {"content": "b", "status": "completed"},
        ],
        "todos_snapshot": [{"content": "a", "status": "in_progress"}],
    }

    result = await middleware.aafter_agent(cast(Any, state), _runtime())

    assert result == {"todos": [], "todos_snapshot": []}


@pytest.mark.asyncio
async def test_no_clear_while_work_remains():
    middleware = TodoMiddleware()
    state = {
        "todos": [
            {"content": "a", "status": "completed"},
            {"content": "b", "status": "in_progress"},
        ]
    }

    result = await middleware.aafter_agent(cast(Any, state), _runtime())

    assert result is None


@pytest.mark.asyncio
async def test_orphan_snapshot_dropped():
    """A snapshot without a live list (model cleared it) is dropped."""
    middleware = TodoMiddleware()
    state = {"todos": [], "todos_snapshot": [{"content": "a", "status": "pending"}]}

    result = await middleware.aafter_agent(cast(Any, state), _runtime())

    assert result == {"todos_snapshot": []}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context_kwargs",
    [
        {"entrypoint": AuthorType.WEB, "call_depth": 1},  # sub-agent run
        {"entrypoint": AuthorType.TRIGGER},  # cron run
    ],
)
async def test_after_hooks_skipped_without_live_viewer(context_kwargs):
    """The after-hooks mirror the interactive gate: no state writes for
    sub-agent or cron runs, even if stale todos linger there."""
    middleware = TodoMiddleware()
    state = {
        "todos": [{"content": "a", "status": "completed"}],
        "messages": [],
    }

    assert (
        await middleware.aafter_agent(cast(Any, state), _runtime(context_kwargs))
        is None
    )
    assert (
        await middleware.aafter_model(cast(Any, state), _runtime(context_kwargs))
        is None
    )


@pytest.mark.asyncio
async def test_no_update_when_nothing_to_clear():
    middleware = TodoMiddleware()

    result = await middleware.aafter_agent(cast(Any, {}), _runtime())

    assert result is None


# Snapshot capture at compaction time is covered in test_summarization.py
# (SummarizationMiddleware owns the todos_snapshot write).
