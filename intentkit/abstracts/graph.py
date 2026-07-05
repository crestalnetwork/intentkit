from collections.abc import Callable, Sequence
from enum import Enum
from typing import Annotated, Any, NotRequired

from langchain.agents import AgentState as BaseAgentState
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
from pydantic import BaseModel

from intentkit.models.agent import Agent
from intentkit.models.chat import AuthorType, ChatMessageAttachment


class AgentError(str, Enum):
    """The error types that can be raised by the agent."""

    INSUFFICIENT_CREDITS = "insufficient_credits"


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
    but adds `REMOVE_ALL_MESSAGES` handling so the bundled
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
    __extra__: NotRequired[dict[str, Any]]


class AgentContext(BaseModel):
    agent_id: str
    get_agent: Callable[[], Agent]
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

    @property
    def agent(self) -> Agent:
        return self.get_agent()

    @property
    def is_subagent(self) -> bool:
        """True when this run was invoked by another agent via call_agent."""
        return self.call_depth > 0

    @property
    def thread_id(self) -> str:
        return f"{self.agent_id}-{self.chat_id}"
