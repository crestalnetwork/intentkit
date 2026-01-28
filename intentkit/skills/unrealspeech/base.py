from langchain_core.tools.base import ToolException
from pydantic import Field

from intentkit.skills.base import IntentKitSkill


class UnrealSpeechBaseTool(IntentKitSkill):
    """Base class for UnrealSpeech text-to-speech tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")

    def get_api_key(self):
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        api_key_provider = skill_config.get("api_key_provider")
        if api_key_provider == "agent_owner":
            api_key = skill_config.get("api_key")
            if api_key:
                return api_key
            else:
                raise ToolException("No api_key found in agent_owner configuration")
        else:
            raise ToolException(
                f"Invalid API key provider: {api_key_provider}. Only 'agent_owner' is supported for UnrealSpeech."
            )

    category: str = "unrealspeech"
