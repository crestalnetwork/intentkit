"""HTTP client tools."""

from collections.abc import Callable

from intentkit.tools.http.base import HttpBaseTool
from intentkit.tools.http.get import HttpGet
from intentkit.tools.http.post import HttpPost
from intentkit.tools.http.put import HttpPut

# Cache tools at the system level, because they are stateless
_cache: dict[str, HttpBaseTool] = {}

_TOOL_CLASSES: dict[str, Callable[[], HttpBaseTool]] = {
    "http_get": HttpGet,
    "http_post": HttpPost,
    "http_put": HttpPut,
}


async def get_tools(tool_names: list[str], **_) -> list[HttpBaseTool]:
    """Get the requested HTTP client tools; unknown names are skipped."""
    return [tool for name in tool_names if (tool := get_http_tool(name))]


def get_http_tool(tool_name: str) -> HttpBaseTool | None:
    """Get an HTTP client tool by name, using the instance cache."""
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
