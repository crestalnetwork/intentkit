from langchain_core.tools import BaseTool

from intentkit.tools.jupiter.price import JupiterGetPrice
from intentkit.tools.jupiter.swap import JupiterGetQuote

_TOOL_CLASSES: dict[str, type[BaseTool]] = {
    "jupiter_get_price": JupiterGetPrice,
    "jupiter_get_quote": JupiterGetQuote,
}


async def get_tools(tool_names: list[str], **_) -> list[BaseTool]:
    """Get the requested Jupiter tools; unknown names are skipped."""
    return [_TOOL_CLASSES[name]() for name in tool_names if name in _TOOL_CLASSES]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
