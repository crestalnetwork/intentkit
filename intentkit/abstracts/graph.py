import asyncio
from enum import Enum
from typing import Any, Dict, NotRequired, Optional

from langgraph.prebuilt.chat_agent_executor import AgentState as BaseAgentState
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
class AgentState(BaseAgentState):
    """The state of the agent."""

    context: dict[str, Any]
    error: NotRequired[AgentError]
    __extra__: NotRequired[Dict[str, Any]]


class AgentContext(BaseModel):
    agent_id: str
    chat_id: str
    user_id: Optional[str] = None
    app_id: Optional[str] = None
    entrypoint: AuthorType
    is_private: bool
    payer: Optional[str] = None

    @property
    def agent(self) -> Agent:
        return asyncio.run(Agent.get(self.agent_id))
