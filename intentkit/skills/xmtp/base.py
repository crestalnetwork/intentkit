from typing import Literal

from intentkit.skills.base import IntentKitSkill


class XmtpBaseTool(IntentKitSkill):
    """Base class for XMTP-related skills."""

    # Set response format to content_and_artifact for returning tuple
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    @property
    def category(self) -> str:
        """Return the skill category."""
        return "xmtp"
