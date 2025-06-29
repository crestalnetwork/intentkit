from enum import Enum
from typing import Any, Callable, Dict, NotRequired

from langgraph.prebuilt.chat_agent_executor import AgentState as BaseAgentState


class AgentError(str, Enum):
    """The error types that can be raised by the agent."""

    INSUFFICIENT_CREDITS = "insufficient_credits"


# We create the AgentState that we will pass around
# This simply involves a list of messages
# We want steps to return messages to append to the list
# So we annotate the messages attribute with operator.add
class AgentState(BaseAgentState):
    """The state of the agent."""

    context: dict[str, Any]
    error: NotRequired[AgentError]
    __extra__: NotRequired[Dict[str, Any]]


MemoryManager = Callable[[AgentState], AgentState]
