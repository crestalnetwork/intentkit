from langchain_core.tools import BaseTool

from intentkit.skills.base import SkillConfig
from intentkit.skills.jupiter.price import JupiterGetPrice
from intentkit.skills.jupiter.swap import JupiterGetQuote


class JupiterConfig(SkillConfig):
    api_key: str | None = None


async def get_skills(
    config: JupiterConfig,
    is_private: bool,
    **_,
) -> list[BaseTool]:
    api_key = config.get("api_key")
    return [
        JupiterGetPrice(api_key=api_key),
        JupiterGetQuote(api_key=api_key),
    ]


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return True
