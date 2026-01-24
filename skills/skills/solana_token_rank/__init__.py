from typing import TypedDict
from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.solana_token_rank.base import SolanaTokenRankBaseTool
from skills.solana_token_rank.solana_token_rank import SolanaTokenRank

_cache: dict[str, SolanaTokenRankBaseTool] = {}

class SkillStates(TypedDict):
    solana_token_rank: SkillState

class Config(SkillConfig):
    states: SkillStates

async def get_skills(config: "Config", is_private: bool, store: SkillStoreABC, **_) -> list[SolanaTokenRankBaseTool]:
    available_skills = []
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    return [get_solana_skill(name, store) for name in available_skills]

def get_solana_skill(name: str, store: SkillStoreABC) -> SolanaTokenRankBaseTool:
    if name == "solana_token_rank":
        if name not in _cache:
            _cache[name] = SolanaTokenRank(skill_store=store)
        return _cache[name]
    else:
        raise ValueError(f"Unknown solana_token_rank skill: {name}")
      
