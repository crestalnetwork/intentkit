from intentkit.skills.base import IntentKitSkill


class HttpBaseTool(IntentKitSkill):
    """Base class for HTTP client tools."""

    category: str = "http"
