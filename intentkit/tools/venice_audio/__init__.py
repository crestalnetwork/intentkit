"""Venice Audio text-to-speech tools."""

from intentkit.config.config import config as system_config
from intentkit.tools.venice_audio.base import VeniceAudioBaseTool
from intentkit.tools.venice_audio.venice_audio import VeniceAudioTool

# Cache tools at the module level, because they are stateless
_cache: dict[str, VeniceAudioBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[VeniceAudioBaseTool]] = {
    "venice_audio_text_to_speech": VeniceAudioTool,
    # Add new mappings here: "tool_name": ToolClassName
}


async def get_tools(tool_names: list[str], **_) -> list[VeniceAudioBaseTool]:
    """Return Venice Audio tool instances for the requested names.

    Unknown names are skipped silently.
    """
    tools: list[VeniceAudioBaseTool] = []
    for name in tool_names:
        tool = get_venice_audio_tool(name)
        if tool:
            tools.append(tool)
    return tools


def get_venice_audio_tool(tool_name: str) -> VeniceAudioBaseTool | None:
    """Get a Venice Audio tool by name, with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        return None

    _cache[tool_name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.venice_api_key)
