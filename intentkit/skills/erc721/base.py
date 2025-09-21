"""ERC721 AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class ERC721BaseTool(CDPBaseTool):
    """Base class for ERC721 tools."""

    @property
    def category(self) -> str:
        return "erc721"
