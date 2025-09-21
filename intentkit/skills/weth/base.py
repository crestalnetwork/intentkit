"""WETH AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class WethBaseTool(CDPBaseTool):
    """Base class for WETH tools."""

    @property
    def category(self) -> str:
        return "weth"
