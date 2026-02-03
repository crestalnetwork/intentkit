from intentkit.skills.base import IntentKitSkill

default_nation_api_url = "http://backend-api"


class NationBaseTool(IntentKitSkill):
    """Base class for GitHub tools."""

    category: str = "nation"
