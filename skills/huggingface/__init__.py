from typing import TypedDict
from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.huggingface.base import HuggingFaceBaseTool
from skills.huggingface.sentiment_analysis import SentimentAnalysis

_cache: dict[str, HuggingFaceBaseTool] = {}

class SkillStates(TypedDict):
    sentiment_analysis: SkillState

class Config(SkillConfig):
    states: SkillStates

async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[HuggingFaceBaseTool]:
    available_skills = []
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    return [get_huggingface_skill(name, store) for name in available_skills]

def get_huggingface_skill(name: str, store: SkillStoreABC) -> HuggingFaceBaseTool:
    if name == "sentiment_analysis":
        if name not in _cache:
            _cache[name] = SentimentAnalysis(skill_store=store)
        return _cache[name]
    raise ValueError(f"Unknown HuggingFace skill: {name}")

