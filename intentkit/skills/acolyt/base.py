from langchain_core.tools.base import ToolException
from pydantic import Field

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill

base_url = "https://acolyt-oracle-poc.vercel.app"


class AcolytBaseTool(IntentKitSkill):
    """Base class for Acolyt tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")

    def get_api_key(self):
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        api_key_provider = skill_config.get("api_key_provider")
        if api_key_provider == "platform":
            return config.acolyt_api_key
        # for backward compatibility, may only have api_key in skill_config
        elif skill_config.get("api_key"):
            return skill_config.get("api_key")
        else:
            raise ToolException(
                f"Invalid API key provider: {api_key_provider}, or no api_key in config"
            )

    category: str = "acolyt"
