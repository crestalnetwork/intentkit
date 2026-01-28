"""Superfluid AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class SuperfluidBaseTool(CDPBaseTool):
    """Base class for Superfluid tools."""

    category: str = "superfluid"
