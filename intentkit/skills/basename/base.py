"""Basename AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class BasenameBaseTool(CDPBaseTool):
    """Base class for Basename tools."""

    @property
    def category(self) -> str:
        return "basename"
