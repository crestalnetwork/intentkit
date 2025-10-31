from pydantic import BaseModel, Field

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill

default_nation_api_url = "http://backend-api"


class NationBaseTool(IntentKitSkill):
    """Base class for GitHub tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: type[BaseModel]

    def get_api_key(self) -> str:
        return config.nation_api_key

    def get_base_url(self) -> str:
        if config.nation_api_url:
            return config.nation_api_url
        return default_nation_api_url

    @property
    def category(self) -> str:
        return "nation"
