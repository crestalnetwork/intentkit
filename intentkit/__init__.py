"""IntentKit - Intent-based AI Agent Platform.

A powerful platform for building AI agents with blockchain and cryptocurrency capabilities.
"""

__version__ = "0.10.3"
__author__ = "Ruihua"
__email__ = "ruihua@crestal.network"

# Core components
# Abstract base classes
from .core.engine import stream_agent, stream_agent_raw
from .core.executor import build_executor

__all__ = [
    "stream_agent",
    "build_executor",
    "stream_agent_raw",
]
