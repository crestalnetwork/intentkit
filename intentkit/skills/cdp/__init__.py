"""CDP wallet interaction skills."""

from typing import TypedDict

from coinbase_agentkit import (
    cdp_api_action_provider,
    cdp_evm_wallet_action_provider,
    wallet_action_provider,
)

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import (
    SkillConfig,
    SkillState,
    action_to_structured_tool,
    get_agentkit_actions,
)
from intentkit.skills.cdp.base import CDPBaseTool


class SkillStates(TypedDict):
    WalletActionProvider_get_balance: SkillState
    WalletActionProvider_get_wallet_details: SkillState
    WalletActionProvider_native_transfer: SkillState
    CdpApiActionProvider_request_faucet_funds: SkillState
    CdpEvmWalletActionProvider_get_swap_price: SkillState
    CdpEvmWalletActionProvider_swap: SkillState


class Config(SkillConfig):
    """Configuration for CDP skills."""

    states: SkillStates


# CDP skills is not stateless for agents, so we need agent_id here
# If you are skill contributor, please do not follow this pattern
async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    agent_id: str,
    **_,
) -> list[CDPBaseTool]:
    """Get all CDP skills.

    Args:
        config: The configuration for CDP skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.
        agent_id: The ID of the agent using the skills.

    Returns:
        A list of CDP skills.
    """
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Initialize CDP client
    actions = await get_agentkit_actions(
        agent_id,
        store,
        [
            wallet_action_provider,
            cdp_api_action_provider,
            cdp_evm_wallet_action_provider,
        ],
    )
    tools = []
    for skill in available_skills:
        for action in actions:
            if action.name.endswith(skill):
                tools.append(action_to_structured_tool(action))
    return tools
