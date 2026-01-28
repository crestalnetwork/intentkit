"""ERC721 AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class ERC721BaseTool(CDPBaseTool):
    """Base class for ERC721 tools."""

    category: str = "erc721"
