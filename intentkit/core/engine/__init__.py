"""AI agent execution engine.

Public entry points for running an agent over a chat message, split by
responsibility:

- ``stream``   — orchestration: validation, media prep, the LangGraph
  stream loop and its error handling
- ``chunks``   — persisting model/tool stream chunks and recording expenses
- ``media``    — attachment fetching and multimodal content blocks
- ``content``  — extractors for provider-specific message content
- ``recovery`` — checkpoint cleanup after cancels/empty outputs/corruption
"""

from intentkit.core.engine.content import (
    count_web_searches,
    extract_cached_input_tokens,
    extract_text_content,
    extract_thinking_content,
)
from intentkit.core.engine.stream import (
    execute_agent,
    stream_agent,
    stream_agent_raw,
    thread_stats,
)

__all__ = [
    "count_web_searches",
    "execute_agent",
    "extract_cached_input_tokens",
    "extract_text_content",
    "extract_thinking_content",
    "stream_agent",
    "stream_agent_raw",
    "thread_stats",
]
