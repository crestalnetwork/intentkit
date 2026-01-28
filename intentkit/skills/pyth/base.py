"""Pyth AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class PythBaseTool(CDPBaseTool):
    """Base class for Pyth tools."""

    category: str = "pyth"
