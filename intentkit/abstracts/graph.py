from collections.abc import Callable
from enum import Enum
from typing import Any, NotRequired

from langchain.agents import AgentState as BaseAgentState
from pydantic import BaseModel

from intentkit.models.agent import Agent
from intentkit.models.chat import AuthorType


class AgentError(str, Enum):
    """The error types that can be raised by the agent."""

    INSUFFICIENT_CREDITS = "insufficient_credits"


# We create the AgentState that we will pass around
# This simply involves a list of messages
# We want steps to return messages to append to the list
# So we annotate the messages attribute with operator.add
class AgentState(BaseAgentState[Any]):
    """The state of the agent."""

    context: dict[str, Any]
    error: NotRequired[AgentError]
    __extra__: NotRequired[dict[str, Any]]


class AgentContext(BaseModel):
    agent_id: str
    get_agent: Callable[[], Agent]
    chat_id: str
    user_id: str | None = None
    app_id: str | None = None
    entrypoint: AuthorType
    is_private: bool
    search: bool = False
    thinking: bool = False
    payer: str | None = None

    @property
    def agent(self) -> Agent:
        return self.get_agent()

    @property
    def thread_id(self) -> str:
        return f"{self.agent_id}-{self.chat_id}"
