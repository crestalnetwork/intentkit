"""Web3 skills."""

from abstracts.skill import SkillStoreABC
from app.core.system import SystemStore
from utils.chain import ChainProvider

from .base import Web3BaseTool
from .block import GetCurrentBlock
from .network import GetNetworks
from .token import GetToken, GetWellknownTokens
from .transfer import GetTransfers


def get_web3_skill(
    name: str,
    chain_provider: ChainProvider,
    system_store: SystemStore,
    skill_store: SkillStoreABC,
    agent_store: SkillStoreABC,
    agent_id: str,
) -> Web3BaseTool:

    if name == "get_networks":
        return GetNetworks(
            chain_provider=chain_provider,
            agent_id=agent_id,
            system_store=system_store,
            skill_store=skill_store,
            agent_store=agent_store,
        )

    if name == "get_wellknown_tokens":
        return GetWellknownTokens(
            chain_provider=chain_provider,
            agent_id=agent_id,
            system_store=system_store,
            skill_store=skill_store,
            agent_store=agent_store,
        )

    if name == "get_token":
        return GetToken(
            chain_provider=chain_provider,
            agent_id=agent_id,
            system_store=system_store,
            skill_store=skill_store,
            agent_store=agent_store,
        )

    if name == "get_received_transfers":
        return GetTransfers(
            chain_provider=chain_provider,
            agent_id=agent_id,
            system_store=system_store,
            skill_store=skill_store,
            agent_store=agent_store,
        )

    if name == "get_current_block":
        return GetCurrentBlock(
            chain_provider=chain_provider,
            agent_id=agent_id,
            system_store=system_store,
            skill_store=skill_store,
            agent_store=agent_store,
        )

    else:
        raise ValueError(f"Unknown Web3 skill: {name}")
