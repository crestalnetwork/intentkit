from typing import Callable, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep, RemainingSteps
from typing_extensions import Annotated, TypedDict


# We create the AgentState that we will pass around
# This simply involves a list of messages
# We want steps to return messages to append to the list
# So we annotate the messages attribute with operator.add
class AgentState(TypedDict):
    """The state of the agent."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    need_clear: bool
    is_last_step: IsLastStep
    remaining_steps: RemainingSteps


MemoryManager = Callable[[AgentState], AgentState]
