"""Casino tools for card games and dice rolling."""

from typing import Any

from intentkit.tools.casino.base import CasinoBaseTool
from intentkit.tools.casino.deck_draw import CasinoDeckDraw
from intentkit.tools.casino.deck_shuffle import CasinoDeckShuffle
from intentkit.tools.casino.dice_roll import CasinoDiceRoll

# Cache tools at the system level, because they are stateless
_cache: dict[str, CasinoBaseTool] = {}

_TOOL_CLASSES: dict[str, type[CasinoBaseTool]] = {
    "casino_deck_shuffle": CasinoDeckShuffle,
    "casino_deck_draw": CasinoDeckDraw,
    "casino_dice_roll": CasinoDiceRoll,
}


async def get_tools(tool_names: list[str], **_: Any) -> list[CasinoBaseTool]:
    """Return Casino tool instances for the requested names."""
    result: list[CasinoBaseTool] = []
    for name in tool_names:
        tool = get_casino_tool(name)
        if tool:
            result.append(tool)
    return result


def get_casino_tool(name: str) -> CasinoBaseTool | None:
    """Get a Casino tool by name."""
    tool_class = _TOOL_CLASSES.get(name)
    if tool_class is None:
        return None
    if name not in _cache:
        _cache[name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
