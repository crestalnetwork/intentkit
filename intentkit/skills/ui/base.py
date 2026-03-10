from typing import Literal

from intentkit.skills.base import IntentKitSkill


class UIBaseTool(IntentKitSkill):
    """Base class for UI-related skills."""

    category: str = "ui"

    # Set response format to content_and_artifact for returning tuple
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
