from collections.abc import Callable

from intentkit.tools.github.base import GitHubBaseTool
from intentkit.tools.github.github_search import GitHubSearch

# Cache tools at the system level, because they are stateless
_cache: dict[str, GitHubBaseTool] = {}

_TOOL_CLASSES: dict[str, Callable[[], GitHubBaseTool]] = {
    "github_search": GitHubSearch,
}


async def get_tools(tool_names: list[str], **_) -> list[GitHubBaseTool]:
    """Get the requested GitHub tools; unknown names are skipped."""
    return [tool for name in tool_names if (tool := get_github_tool(name))]


def get_github_tool(tool_name: str) -> GitHubBaseTool | None:
    """Get a GitHub tool by name, using the instance cache."""
    if tool_name in _cache:
        return _cache[tool_name]
    cls = _TOOL_CLASSES.get(tool_name)
    if cls is None:
        return None
    _cache[tool_name] = cls()
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
