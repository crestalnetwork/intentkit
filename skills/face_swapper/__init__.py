# intentkit/skills/face_swapper/__init__.py

from typing import TypedDict
from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.face_swapper.base import FaceSwapperBaseTool
from skills.face_swapper.face_swap import FaceSwapTool

_cache: dict[str, FaceSwapperBaseTool] = {}

class SkillStates(TypedDict):
    face_swap: SkillState

class Config(SkillConfig):
    """Configuration for face swap skills."""
    states: SkillStates

async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[FaceSwapperBaseTool]:
    available_skills = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    return [get_face_swapper_skill(name, store) for name in available_skills]

def get_face_swapper_skill(name: str, store: SkillStoreABC) -> FaceSwapperBaseTool:
    if name == "face_swap":
        if name not in _cache:
            _cache[name] = FaceSwapTool(skill_store=store)
        return _cache[name]
    else:
        raise ValueError(f"Unknown face swap skill: {name}")
