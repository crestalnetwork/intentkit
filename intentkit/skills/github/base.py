from intentkit.skills.base import IntentKitSkill


class GitHubBaseTool(IntentKitSkill):
    """Base class for GitHub tools."""

    category: str = "github"
