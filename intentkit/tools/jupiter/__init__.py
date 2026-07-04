from typing import TypedDict

from langchain_core.tools import BaseTool

from intentkit.tools.base import ToolsetConfig, ToolState, filter_enabled_tool_names
from intentkit.tools.jupiter.price import JupiterGetPrice
from intentkit.tools.jupiter.swap import JupiterGetQuote


class ToolStates(TypedDict):
    jupiter_get_price: ToolState
    jupiter_get_quote: ToolState


class Config(ToolsetConfig):
    """Configuration for Jupiter tools."""

    states: ToolStates


_TOOL_CLASSES: dict[str, type[BaseTool]] = {
    "jupiter_get_price": JupiterGetPrice,
    "jupiter_get_quote": JupiterGetQuote,
}


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[BaseTool]:
    return [
        _TOOL_CLASSES[name]()
        for name in filter_enabled_tool_names(config.get("states", {}), is_private)
        if name in _TOOL_CLASSES
    ]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
