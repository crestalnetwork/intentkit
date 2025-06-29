from typing import Callable, List

from pydantic import BaseModel


class AgentMessageInput(BaseModel):
    """Input message model for AI agent interactions.

    This class represents the structured input that can be sent to an AI agent,
    supporting both text-based queries and image-based inputs for multimodal
    interactions.

    Attributes:
        text (str): The main text content of the message or query
        images (List[str]): List of image references/URLs to be processed by the agent.
                           Empty list if no images are provided.
    """

    text: str  # required
    """The main text content or query to be processed by the agent"""

    images: List[str] = []  # optional, defaults to empty list
    """List of image references or URLs for multimodal processing"""


# Define a type hint for the callback that takes three strings and returns a list of strings
AgentExecutionCallback = Callable[[str, AgentMessageInput, str], List[str]]
"""Callback function type for agent execution.

Args:
    aid (str): The agent ID that uniquely identifies the AI agent
    message (AgentMessageInput): The input message containing text and optional images
    thread_id (str): The thread ID for tracking the conversation context

Returns:
    List[str]: A list of formatted response lines from the agent execution. Each line
        typically contains input/output markers, agent responses, and timing information.
"""
