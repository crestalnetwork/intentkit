import logging
from typing import Optional, TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.venice_audio.base import VeniceAudioBaseTool
from skills.venice_audio.venice_audio import VeniceAudioTool

logger = logging.getLogger(__name__)


_cache: dict[str, VeniceAudioBaseTool] = {}


class SkillStates(TypedDict):
    af_alloy: SkillState
    af_aoede: SkillState
    af_bella: SkillState
    af_heart: SkillState
    af_jadzia: SkillState
    af_jessica: SkillState
    af_kore: SkillState
    af_nicole: SkillState
    af_nova: SkillState
    af_river: SkillState
    af_sarah: SkillState
    af_sky: SkillState
    am_adam: SkillState
    am_echo: SkillState
    am_eric: SkillState
    am_fenrir: SkillState
    am_liam: SkillState
    am_michael: SkillState
    am_onyx: SkillState
    am_puck: SkillState
    am_santa: SkillState
    bf_alice: SkillState
    bf_emma: SkillState
    bf_lily: SkillState
    bm_daniel: SkillState
    bm_fable: SkillState
    bm_george: SkillState
    bm_lewis: SkillState
    ef_dora: SkillState
    em_alex: SkillState
    em_santa: SkillState
    ff_siwis: SkillState
    hf_alpha: SkillState
    hf_beta: SkillState
    hm_omega: SkillState
    hm_psi: SkillState
    if_sara: SkillState
    im_nicola: SkillState
    jf_alpha: SkillState
    jf_gongitsune: SkillState
    jf_nezumi: SkillState
    jf_tebukuro: SkillState
    jm_kumo: SkillState
    pf_dora: SkillState
    pm_alex: SkillState
    pm_santa: SkillState
    zf_xiaobei: SkillState
    zf_xiaoni: SkillState
    zf_xiaoxiao: SkillState
    zf_xiaoyi: SkillState
    zm_yunjian: SkillState
    zm_yunxi: SkillState
    zm_yunxia: SkillState
    zm_yunyang: SkillState


class Config(SkillConfig):
    enabled: bool
    api_key: str  # API Key may be optional if provided system-wide
    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,  # Allow for extra arguments if the loader passes them
) -> list[VeniceAudioBaseTool]:
    """
    Factory function to create and return Venice Audio skill tools.

    Args:
        config: The configuration dictionary for the Venice Audio skill.
        skill_store: The skill store instance.
        agent_id: The ID of the agent requesting the skills.

    Returns:
        A list of VeniceAudioBaseTool instances for the Venice Audio skill.
    """
    # Check if the entire category is disabled first
    if not config.get("enabled", False):
        return []

    available_skills: list[VeniceAudioBaseTool] = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    result = []
    for name in available_skills:
        skill = get_venice_audio_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_venice_audio_skill(
    name: str,
    store: SkillStoreABC,
) -> Optional[VeniceAudioBaseTool]:
    """
    Factory function to get a cached Venice Audio skill instance by name.

    Args:
        name: The name of the skill to get (must match keys in _SKILL_NAME_TO_CLASS_MAP).
        store: The skill store, passed to the skill constructor.

    Returns:
        The requested Venice Audio skill instance, or None if the name is unknown.
    """

    # Return from cache immediately if already exists
    if name in _cache:
        return _cache[name]

    # Cache and return the newly created instance
    _cache[name] = VeniceAudioTool(
        skill_store=store,
        voice_model=name,
    )
    return _cache[name]
