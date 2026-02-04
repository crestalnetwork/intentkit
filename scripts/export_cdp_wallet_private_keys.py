import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("cdp_wallet_private_keys.json")


def normalize_private_key(private_key: str) -> str:
    cleaned = private_key.strip()
    if not cleaned:
        return cleaned
    if cleaned.startswith(("0x", "0X")):
        return "0x" + cleaned[2:]
    return "0x" + cleaned


def make_output_entry(
    agent_id: str,
    wallet_address: str,
    private_key: str,
    network_id: str | None,
) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "wallet_address": wallet_address,
        "private_key": private_key,
        "network_id": network_id,
    }


async def export_wallet_private_key(cdp_client: Any, address: str) -> str:
    return await cdp_client.evm.export_account(address=address)


async def main() -> None:
    from intentkit.config.config import config
    from intentkit.config.db import get_session, init_db
    from intentkit.models.agent.db import AgentTable
    from intentkit.models.agent_data import AgentDataTable
    from intentkit.wallets.cdp import get_cdp_client

    await init_db(**config.db)
    cdp_client = get_cdp_client()

    async with get_session() as session:
        result = await session.execute(
            select(AgentTable, AgentDataTable)
            .outerjoin(AgentDataTable, AgentDataTable.id == AgentTable.id)
            .where(AgentTable.wallet_provider == "cdp")
        )
        rows = result.all()

    exported: list[dict[str, Any]] = []
    for agent_row, agent_data in rows:
        if not agent_data or not agent_data.evm_wallet_address:
            logger.info("%s None export skip:no_wallet", agent_row.id)
            continue
        wallet_address = agent_data.evm_wallet_address
        try:
            private_key = await export_wallet_private_key(cdp_client, wallet_address)
        except Exception as exc:
            logger.info("%s %s export error:%s", agent_row.id, wallet_address, str(exc))
            continue
        exported.append(
            make_output_entry(
                agent_id=agent_row.id,
                wallet_address=wallet_address,
                private_key=normalize_private_key(private_key),
                network_id=agent_row.network_id,
            )
        )
        logger.info("%s %s export ok", agent_row.id, wallet_address)

    OUTPUT_PATH.write_text(json.dumps(exported, indent=2), encoding="utf-8")
    logger.info("saved %s", OUTPUT_PATH)


if __name__ == "__main__":
    asyncio.run(main())
