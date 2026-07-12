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
    SummarizationMiddleware,
    TodoMiddleware,
    ToolBindingMiddleware,
)
from intentkit.core.system_tools import current_time, write_todos
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
    assert write_todos.main_agent_only is True
    assert write_todos.context_editing_exempt is True
    assert write_todos.interactive_only is False
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
# ToolBindingMiddleware gating (main_agent_only)
# ──────────────────────────────────────────────


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


async def _bound_tool_names(context: AgentContext) -> set[str]:
    llm_model = MagicMock()
    llm_model.create_instance = AsyncMock(return_value=MagicMock())
    middleware = ToolBindingMiddleware(llm_model, [current_time, write_todos])
    request = _FakeRequest(context)
    handler = AsyncMock(return_value="response")
    await middleware.awrap_model_call(cast(Any, request), handler)
    handler.assert_awaited_once()
    return {t.name for t in request.overridden["tools"]}


@pytest.mark.asyncio
async def test_write_todos_bound_for_live_channels():
    names = await _bound_tool_names(_make_context(AuthorType.WEB))
    assert "write_todos" in names


@pytest.mark.asyncio
async def test_write_todos_kept_for_cron_trigger():
    """Unlike interactive_only tools, todo planning stays on for cron runs."""
    names = await _bound_tool_names(_make_context(AuthorType.TRIGGER))
    assert "write_todos" in names


@pytest.mark.asyncio
async def test_write_todos_dropped_for_subagent():
    names = await _bound_tool_names(_make_context(AuthorType.TELEGRAM, call_depth=1))
    assert "write_todos" not in names
    assert "current_time" in names


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
async def test_todo_prompt_skipped_for_subagent():
    middleware = TodoMiddleware()
    request = _FakeRequest(
        _make_context(AuthorType.WEB, call_depth=1),
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

    result = await middleware.aafter_model(cast(Any, state), cast(Any, None))

    assert result is not None
    errors = result["messages"]
    assert len(errors) == 2
    assert {e.tool_call_id for e in errors} == {"a", "b"}
    assert all(e.status == "error" for e in errors)


@pytest.mark.asyncio
async def test_single_write_todos_allowed():
    middleware = TodoMiddleware()
    state = {"messages": [AIMessage(content="", tool_calls=[_tool_call("a")])]}

    result = await middleware.aafter_model(cast(Any, state), cast(Any, None))

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

    result = await middleware.aafter_agent(cast(Any, state), cast(Any, None))

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

    result = await middleware.aafter_agent(cast(Any, state), cast(Any, None))

    assert result is None


@pytest.mark.asyncio
async def test_orphan_snapshot_dropped():
    """A snapshot without a live list (model cleared it) is dropped."""
    middleware = TodoMiddleware()
    state = {"todos": [], "todos_snapshot": [{"content": "a", "status": "pending"}]}

    result = await middleware.aafter_agent(cast(Any, state), cast(Any, None))

    assert result == {"todos_snapshot": []}


@pytest.mark.asyncio
async def test_no_update_when_nothing_to_clear():
    middleware = TodoMiddleware()

    result = await middleware.aafter_agent(cast(Any, {}), cast(Any, None))

    assert result is None


# ──────────────────────────────────────────────
# SummarizationMiddleware: snapshot capture at compaction
# ──────────────────────────────────────────────


def test_snapshot_added_when_summarization_runs():
    todos = [{"content": "a", "status": "in_progress"}]
    result = SummarizationMiddleware._with_todos_snapshot(
        cast(Any, {"todos": todos}), {"messages": ["summary"]}
    )

    assert result == {"messages": ["summary"], "todos_snapshot": todos}


def test_snapshot_untouched_when_no_summarization():
    assert (
        SummarizationMiddleware._with_todos_snapshot(
            cast(Any, {"todos": [{"content": "a", "status": "pending"}]}), None
        )
        is None
    )


def test_snapshot_empty_when_no_todos():
    result = SummarizationMiddleware._with_todos_snapshot(
        cast(Any, {}), {"messages": []}
    )

    assert result == {"messages": [], "todos_snapshot": []}
