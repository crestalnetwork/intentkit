from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill


class DappLookerBaseTool(IntentKitSkill):
    """Base class for DappLooker tools."""

    def get_api_key(self):
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        api_key_provider = skill_config.get("api_key_provider")
        if api_key_provider == "platform":
            return config.dapplooker_api_key
        # for backward compatibility, may only have api_key in skill_config
        elif skill_config.get("api_key"):
            return skill_config.get("api_key")
        else:
            raise ToolException(
                f"Invalid API key provider: {api_key_provider}, or no api_key in config"
            )

    category: str = "dapplooker"
