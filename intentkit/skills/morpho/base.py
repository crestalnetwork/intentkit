"""Morpho AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class MorphoBaseTool(CDPBaseTool):
    """Base class for Morpho tools."""

    @property
    def category(self) -> str:
        return "morpho"
