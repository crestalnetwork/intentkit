"""Video generation tools, all served through OpenRouter."""

from collections.abc import Callable

from intentkit.config.config import config as system_config
from intentkit.tools.meta import ToolsetMeta
from intentkit.tools.video.base import VideoBaseTool
from intentkit.tools.video.minimax import HailuoVideo
from intentkit.tools.video.seedance import SeedanceMiniVideo, SeedanceVideo

toolset = ToolsetMeta(
    title="Video Generation",
    description="Generate videos from text prompts or images using Seedance and MiniMax models.",
    tags=["Media", "AI"],
    icon="/tools/video/video.svg",
)


# Cache tools at the system level, because they are stateless
_cache: dict[str, VideoBaseTool] = {}

_TOOL_NAME_TO_CLASS: dict[str, Callable[[], VideoBaseTool]] = {
    "video_seedance_mini": SeedanceMiniVideo,
    "video_seedance": SeedanceVideo,
    "video_hailuo": HailuoVideo,
}


async def get_tools(tool_names: list[str], **_) -> list[VideoBaseTool]:
    """Return video generation tool instances for the requested names.

    Unknown names are skipped silently.
    """
    tools: list[VideoBaseTool] = []
    for name in tool_names:
        tool = get_video_tool(name)
        if tool:
            tools.append(tool)
    return tools


def get_video_tool(tool_name: str) -> VideoBaseTool | None:
    """Get a video tool by name, with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    cls = _TOOL_NAME_TO_CLASS.get(tool_name)
    if cls is None:
        return None

    _cache[tool_name] = cls()
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.openrouter_api_key)
