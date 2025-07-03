"""IntentKit - Intent-based AI Agent Platform.

A powerful platform for building AI agents with blockchain and cryptocurrency capabilities.
"""

__version__ = "0.0.1"
__author__ = "hyacinthus"
__email__ = "hyacinthus@gmail.com"

# Core components
# Abstract base classes
from .core.engine import create_agent, stream_agent

__all__ = [
    "create_agent",
    "stream_agent",
]
