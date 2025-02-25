"""Elfa skills."""

from abstracts.skill import SkillStoreABC
from skills.elfa.base import ElfaBaseTool
from skills.elfa.mention import ElfaGetMentions, ElfaGetTopMentions, ElfaSearchMentions
from skills.elfa.stats import ElfaGetSmartStats
from skills.elfa.tokens import ElfaGetTrendingTokens


def get_elfa_skill(
    name: str,
    api_key: str,
    skill_store: SkillStoreABC,
    agent_store: SkillStoreABC,
    agent_id: str,
) -> ElfaBaseTool:
    if not api_key:
        raise ValueError("Elfa API token is empty")

    if name == "get_mentions":
        return ElfaGetMentions(
            api_key=api_key,
            agent_id=agent_id,
            skill_store=skill_store,
            agent_store=agent_store,
        )

    if name == "get_top_mentions":
        return ElfaGetTopMentions(
            api_key=api_key,
            agent_id=agent_id,
            skill_store=skill_store,
            agent_store=agent_store,
        )

    if name == "search_mentions":
        return ElfaSearchMentions(
            api_key=api_key,
            agent_id=agent_id,
            skill_store=skill_store,
            agent_store=agent_store,
        )

    if name == "get_trending_tokens":
        return ElfaGetTrendingTokens(
            api_key=api_key,
            agent_id=agent_id,
            skill_store=skill_store,
            agent_store=agent_store,
        )

    if name == "get_smart_stats":
        return ElfaGetSmartStats(
            api_key=api_key,
            agent_id=agent_id,
            skill_store=skill_store,
            agent_store=agent_store,
        )

    else:
        raise ValueError(f"Unknown Elfa skill: {name}")
