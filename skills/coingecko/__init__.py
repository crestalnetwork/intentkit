from typing import TypedDict

from pydantic import Field

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState

from .base import CoinGeckoBaseTool
from .get_market_chart import GetMarketChart
from .get_token_details import GetTokenDetails

_cache: dict[str, CoinGeckoBaseTool] = {}


class SkillStates(TypedDict):
    get_token_details: SkillState
    get_market_chart: SkillState


class Config(SkillConfig):
    """Configuration for CoinGecko skills"""

    states: SkillStates
    api_key: str = Field(
        default="", description="Optional API key for premium features"
    )


async def get_skills(
    config: "Config", is_private: bool, store: SkillStoreABC, **_
) -> list[CoinGeckoBaseTool]:
    available_skills = []
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    return [
        get_coingecko_skill(name, store, config.api_key) for name in available_skills
    ]


def get_coingecko_skill(
    name: str, store: SkillStoreABC, api_key: str = ""
) -> CoinGeckoBaseTool:
    if name not in _cache:
        if name == "get_token_details":
            _cache[name] = GetTokenDetails(skill_store=store, api_key=api_key)
        elif name == "get_market_chart":
            _cache[name] = GetMarketChart(skill_store=store, api_key=api_key)
        else:
            raise ValueError(f"Unknown CoinGecko skill: {name}")
    return _cache[name]
