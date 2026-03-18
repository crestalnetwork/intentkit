from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill


class UnrealSpeechBaseTool(IntentKitSkill):
    """Base class for UnrealSpeech text-to-speech tools."""

    def get_api_key(self):
        if not config.unrealspeech_api_key:
            raise ToolException("UnrealSpeech API key is not configured")
        return config.unrealspeech_api_key

    category: str = "unrealspeech"
