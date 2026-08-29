"""Music generation tools."""

from collections.abc import Callable

from intentkit.config.config import config as system_config
from intentkit.tools.meta import ToolsetMeta
from intentkit.tools.music.base import MusicBaseTool
from intentkit.tools.music.minimax import MiniMaxMusicGeneration

toolset = ToolsetMeta(
    title="Music Generation",
    description="Generate songs from prompts and lyrics.",
    tags=["AI", "Audio"],
    icon="/tools/music/music.svg",
)

_cache: dict[str, MusicBaseTool] = {}

_TOOL_NAME_TO_CLASS: dict[str, Callable[[], MusicBaseTool]] = {
    "music_minimax_generate": MiniMaxMusicGeneration,
}


async def get_tools(tool_names: list[str], **_) -> list[MusicBaseTool]:
    """Return requested music generation tools and skip unknown names."""
    return [tool for name in tool_names if (tool := get_music_tool(name))]


def get_music_tool(tool_name: str) -> MusicBaseTool | None:
    """Get a cached music generation tool by name."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS.get(tool_name)
    if tool_class is None:
        return None

    _cache[tool_name] = tool_class()
    return _cache[tool_name]


def available() -> bool:
    """Check whether the music generation API is configured."""
    return bool(system_config.minimax_plan_api_key)
