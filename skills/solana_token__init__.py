from typing import TypedDict
from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.solana_token.base import SolanaTokenBaseSkill
from skills.solana_token.solana_token_rank import SolanaTokenRank

_cache: dict[str, SolanaTokenBaseSkill] = {}

class SkillStates(TypedDict):
    solana_token_rank: SkillState

class Config(SkillConfig):
    states: SkillStates
    helius_api_key: str

async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[SolanaTokenBaseSkill]:
    enabled_skills = []
    for name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            enabled_skills.append(name)

    return [get_solana_token_skill(name, store, config) for name in enabled_skills]

def get_solana_token_skill(name: str, store: SkillStoreABC, config: Config) -> SolanaTokenBaseSkill:
    if name == "solana_token_rank":
        if name not in _cache:
            _cache[name] = SolanaTokenRank(skill_store=store)
            _cache[name].set_config(config)
        return _cache[name]
    raise ValueError(f"Unknown skill name: {name}")
  
