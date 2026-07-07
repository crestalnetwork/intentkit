"""System tools for IntentKit agents.

These tools wrap core functionality and are available to all agents
without additional configuration. Each tool is a cached singleton instance
that can be imported directly where needed.
"""

from intentkit.core.system_tools.base import SystemTool
from intentkit.core.system_tools.call_agent import CallAgentTool
from intentkit.core.system_tools.create_activity import CreateActivityTool
from intentkit.core.system_tools.create_post import CreatePostTool
from intentkit.core.system_tools.current_time import CurrentTimeTool
from intentkit.core.system_tools.get_post import GetPostTool
from intentkit.core.system_tools.read_webpage import ReadWebpageCloudflareTool
from intentkit.core.system_tools.recent_activities import RecentActivitiesTool
from intentkit.core.system_tools.recent_posts import RecentPostsTool
from intentkit.core.system_tools.search_web import WebSearchTool
from intentkit.core.system_tools.store_image import StoreImageTool
from intentkit.core.system_tools.ui_ask_user import UIAskUserTool
from intentkit.core.system_tools.ui_show_card import UIShowCardTool
from intentkit.core.system_tools.update_memory import UpdateMemoryTool

__all__ = [
    "SystemTool",
    "call_agent",
    "create_activity",
    "create_post",
    "current_time",
    "get_post",
    "read_webpage_cloudflare",
    "recent_activities",
    "recent_posts",
    "store_image",
    "ui_ask_user",
    "ui_show_card",
    "update_memory",
    "web_search",
]

# Cached singleton instances — import these directly where needed.
call_agent = CallAgentTool()
create_activity = CreateActivityTool()
create_post = CreatePostTool()
current_time = CurrentTimeTool()
get_post = GetPostTool()
read_webpage_cloudflare = ReadWebpageCloudflareTool()
recent_activities = RecentActivitiesTool()
recent_posts = RecentPostsTool()
store_image = StoreImageTool()
ui_ask_user = UIAskUserTool()
ui_show_card = UIShowCardTool()
update_memory = UpdateMemoryTool()
web_search = WebSearchTool()
