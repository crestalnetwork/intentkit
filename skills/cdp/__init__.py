"""CDP skills."""

from cdp import Wallet

from abstracts.skill import SkillStoreABC
from skills.cdp.base import CdpBaseTool
from skills.cdp.tx import CdpBroadcastEnsoTx


def get_cdp_skill(
    name: str,
    wallet: Wallet,
    store: SkillStoreABC,
    agent_id: str,
) -> CdpBaseTool:
    if not wallet:
        raise ValueError("CDP wallet is empty")

    if name == "broadcast_enso_tx":
        return CdpBroadcastEnsoTx(
            wallet=wallet,
            store=store,
            agent_id=agent_id,
        )

    else:
        raise ValueError(f"Unknown CDP skill: {name}")
