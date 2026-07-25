from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain.agents import AgentState as BaseAgentState
from langchain.agents.middleware.types import OmitFromInput
from langchain_core.messages import AnyMessage, RemoveMessage
from langgraph.channels.delta import DeltaChannel

# `_messages_delta_reducer` is upstream's batching-invariant counterpart of
# `add_messages` for use with `DeltaChannel`. It is private (leading underscore)
# but is documented in its own docstring with a `DeltaChannel` usage example —
# treat as semi-public within the `langgraph>=1.2,<2` pin.
from langgraph.graph.message import (
    REMOVE_ALL_MESSAGES,
    _messages_delta_reducer,  # pyright: ignore[reportPrivateUsage]
)
from pydantic import BaseModel, Field, field_validator

from intentkit.models.agent import Agent
from intentkit.models.chat import (
    AuthorType,
    ChatMessage,
    ChatMessageAttachment,
    ChatMessageCreate,
)


class AgentError(str, Enum):
    """The error types that can be raised by the agent."""

    INSUFFICIENT_CREDITS = "insufficient_credits"


class Todo(TypedDict):
    """A single todo item managed by the `write_todos` system tool."""

    content: str
    """The content/description of the todo item."""

    status: Literal["pending", "in_progress", "completed"]
    """The current status of the todo item."""


def _messages_reducer(
    state: list[AnyMessage], writes: Sequence[Any]
) -> list[AnyMessage]:
    """Batching-invariant messages reducer for `DeltaChannel`.

    Wraps `_messages_delta_reducer` to add `REMOVE_ALL_MESSAGES` handling,
    which the upstream batched reducer documents as out-of-scope. Without
    this wrapper, `SummarizationMiddleware` (which emits
    `[RemoveMessage(REMOVE_ALL_MESSAGES), summary, ...preserved]`) silently
    no-ops the reset and the message list grows unbounded.

    Strategy: flatten writes once, find the *last* `REMOVE_ALL_MESSAGES`
    sentinel. If present, reset state to empty and delegate to the upstream
    reducer with only the post-sentinel writes — preserves batching
    invariance (`reduce(reduce(s, A), B) == reduce(s, A+B)`) across all
    combinations of resets and normal writes.
    """
    flat: list[Any] = []
    for w in writes:
        if isinstance(w, list):
            flat.extend(w)
        else:
            flat.append(w)
    last_reset = -1
    for i, m in enumerate(flat):
        if isinstance(m, RemoveMessage) and m.id == REMOVE_ALL_MESSAGES:
            last_reset = i
    if last_reset >= 0:
        return _messages_delta_reducer([], [flat[last_reset + 1 :]])
    return _messages_delta_reducer(state, writes)  # pyright: ignore[reportArgumentType]


class AgentState(BaseAgentState[Any]):
    """The state of the agent.

    `messages` is overridden to use `DeltaChannel` so checkpointing stores
    incremental writes rather than a full snapshot per step — for long chat
    threads this turns O(N^2) checkpoint growth into O(N). `_messages_reducer`
    delegates to the upstream batching-invariant `_messages_delta_reducer`
    but adds `REMOVE_ALL_MESSAGES` handling so the
    `SummarizationMiddleware` reset path still works.

    `snapshot_frequency=50` is tuned for chat workloads (a few-to-dozens of
    steps per thread) rather than the upstream default of 1000 which targets
    long workflow graphs. 50 caps resume-replay cost at one short reducer
    pass while keeping snapshot writes rare for typical conversations.
    """

    messages: Annotated[
        list[AnyMessage],
        DeltaChannel(_messages_reducer, snapshot_frequency=50),
    ]
    context: dict[str, Any]
    error: NotRequired[AgentError]
    step_count: NotRequired[int]
    todos: Annotated[NotRequired[list[Todo]], OmitFromInput]
    """Current todo list, replaced wholesale by each `write_todos` call."""
    todos_snapshot: Annotated[NotRequired[list[Todo]], OmitFromInput]
    """Copy of `todos` taken when summarization compacts the conversation.

    Between compactions the model sees the list through `write_todos` tool
    results in the message history; summarization destroys those, so this
    snapshot is re-injected into the system prompt. It is refreshed ONLY at
    compaction time to keep the system prompt stable for prompt caching.
    """
    last_llm_at: Annotated[NotRequired[float], OmitFromInput]
    """Unix timestamp of the most recent LLM request in this thread.

    Refreshed before every model call; history compression reads the
    previous value to pick its idle-time threshold tier (windows and
    thresholds defined in `intentkit.core.summarization` and
    `LLMModelInfo.compress_thresholds`).
    """
    __extra__: NotRequired[dict[str, Any]]


class AgentContext(BaseModel):
    agent_id: str
    get_agent: Callable[[], Agent]
    # Runs a nested agent turn to completion. Injected by the engine when it
    # builds the context, so tools that delegate (call_agent) never import
    # intentkit.core.engine — that import closed a core import cycle.
    execute_agent: (
        Callable[[ChatMessageCreate], Awaitable[list[ChatMessage]]] | None
    ) = None
    chat_id: str
    user_id: str | None = None
    team_id: str | None = None
    app_id: str | None = None
    # Original user entry channel (web/telegram/trigger/...), inherited across
    # call_agent chains. Never INTERNAL — use is_subagent to detect delegation.
    entrypoint: AuthorType
    # True when the agent is operated by its owning team: the owner user, a
    # member of the owning team, or the system user. False when a stranger
    # talks to a published agent. Gates team-facing system tools and wallet
    # signing — a guest conversation must never operate the team's assets.
    is_own_team: bool
    thinking: bool = False
    payer: str | None = None
    start_message_id: str = ""
    start_message_attachments: list[ChatMessageAttachment] | None = None
    call_depth: int = 0
    # Frozen at context creation (once per run). Prompt builders must use this
    # instead of the current time: the system prompt is rebuilt on every model
    # call, and a changing timestamp breaks provider prefix caching for the
    # whole conversation after it.
    run_started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("run_started_at")
    @classmethod
    def _run_started_at_utc(cls, v: datetime) -> datetime:
        """Normalize to UTC-aware: prompt builders render it with a hardcoded
        "UTC" suffix. Naive values come from drivers (SQLite) that drop the
        tzinfo of stored-as-UTC columns, so attach UTC rather than convert."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @property
    def agent(self) -> Agent:
        return self.get_agent()

    @property
    def is_subagent(self) -> bool:
        """True when this run was invoked by another agent via call_agent."""
        return self.call_depth > 0

    @property
    def is_interactive(self) -> bool:
        """True when a live user is watching the conversation — not a cron
        TRIGGER run and not a sub-agent run. Gates interactive_only tools
        and the todo prompt guidance."""
        return self.entrypoint != AuthorType.TRIGGER and not self.is_subagent

    @property
    def thread_id(self) -> str:
        return f"{self.agent_id}-{self.chat_id}"
