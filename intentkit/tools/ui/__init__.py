"""UI tools."""

from intentkit.tools.meta import ToolsetMeta
from intentkit.tools.ui.ask_user import UIAskUser
from intentkit.tools.ui.base import UIBaseTool
from intentkit.tools.ui.show_card import UIShowCard

toolset = ToolsetMeta(
    title="UI Components",
    description="Display rich UI components to users such as interactive cards and multiple-choice options. These tools enable agents to present structured, visually appealing content instead of plain text.",
    tags=["Communication", "Infrastructure"],
    icon="/tools/ui/ui.svg",
)


# Cache tools at the module level, because they are stateless
_cache: dict[str, UIBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[UIBaseTool]] = {
    "ui_show_card": UIShowCard,
    "ui_ask_user": UIAskUser,
}


async def get_tools(tool_names: list[str], **_) -> list[UIBaseTool]:
    """Return UI tool instances for the requested names.

    Unknown names are skipped silently.
    """
    tools: list[UIBaseTool] = []
    for name in tool_names:
        tool = get_ui_tool(name)
        if tool:
            tools.append(tool)
    return tools


def get_ui_tool(tool_name: str) -> UIBaseTool | None:
    """Get a UI tool by name, with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        return None

    _cache[tool_name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
