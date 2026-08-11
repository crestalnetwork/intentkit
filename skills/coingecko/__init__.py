from typing import TypedDict, List
from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.coingecko.base import CoinGeckoBaseTool
from skills.coingecko.crypto_price_checker import CryptoPriceChecker


# Cache to store skill instances (skills are stateless)
_cache: dict[str, CoinGeckoBaseTool] = {}


class SkillStates(TypedDict):
    crypto_price_checker: SkillState


class Config(SkillConfig):
    """Configuration for CoinGecko skills."""
    states: SkillStates


async def get_skills(
    config: Config,
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> List[CoinGeckoBaseTool]:
    """Retrieve all allowed CoinGecko skills based on configuration."""
    available_skills = []

    # Check allowed skills based on status (public/private/disabled)
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    return [get_coingecko_skill(name, store) for name in available_skills]


def get_coingecko_skill(
    name: str,
    store: SkillStoreABC,
) -> CoinGeckoBaseTool:
    """Retrieve a CoinGecko skill by name."""
    if name == "crypto_price_checker":
        if name not in _cache:
            _cache[name] = CryptoPriceChecker(skill_store=store)
        return _cache[name]
    else:
        raise ValueError(f"Unknown CoinGecko skill: {name}")
