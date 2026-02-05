import asyncio
import logging
import os
import sys
from decimal import Decimal

from sqlalchemy import select
from web3 import Web3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
USDC_DECIMALS = 6


def format_token_amount(amount: Decimal, decimals: int) -> str:
    text = f"{amount:.{decimals}f}"
    text = text.rstrip("0").rstrip(".")
    return text if text else "0"


async def get_balances(
    wallet_address: str,
    network_id: str,
) -> tuple[Decimal, Decimal]:
    from intentkit.skills.erc20.constants import ERC20_ABI, TOKEN_ADDRESSES_BY_SYMBOLS
    from intentkit.wallets.web3 import get_web3_client

    if not wallet_address:
        return Decimal(0), Decimal(0)

    try:
        web3_client = get_web3_client(network_id)
        checksum_address = Web3.to_checksum_address(wallet_address)

        # ETH Balance
        eth_wei = web3_client.eth.get_balance(checksum_address)
        eth_balance = Decimal(eth_wei) / Decimal(10**18)

        # USDC Balance
        usdc_balance = Decimal(0)
        token_address = TOKEN_ADDRESSES_BY_SYMBOLS.get(network_id, {}).get("USDC")
        if token_address:
            contract = web3_client.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ERC20_ABI,
            )
            usdc_raw = contract.functions.balanceOf(checksum_address).call()
            usdc_balance = Decimal(usdc_raw) / Decimal(10**USDC_DECIMALS)

        return eth_balance, usdc_balance
    except Exception as e:
        logger.error(f"Error checking balance for {wallet_address}: {e}")
        return Decimal(0), Decimal(0)


async def main() -> None:
    from intentkit.config.config import config
    from intentkit.config.db import get_session, init_db
    from intentkit.models.agent.db import AgentTable
    from intentkit.models.agent_data import AgentDataTable

    await init_db(**config.db)

    print(
        f"{'Agent ID':<22} | {'Owner ID':<15} | {'Wallet Address':<42} | {'ETH':<10} | {'USDC':<10}"
    )
    print("-" * 110)

    async with get_session() as session:
        result = await session.execute(
            select(AgentTable, AgentDataTable)
            .outerjoin(AgentDataTable, AgentDataTable.id == AgentTable.id)
            .where(AgentTable.wallet_provider == "cdp")
        )
        rows = result.all()

    found_count = 0
    for agent_row, agent_data in rows:
        # Pydantic validation (optional, stripped for speed)
        agent_id = agent_row.id
        owner_id = agent_row.owner
        network_id = str(agent_row.network_id)

        wallet_addr = agent_data.evm_wallet_address if agent_data else None

        if not wallet_addr:
            continue

        eth, usdc = await get_balances(wallet_addr, network_id)

        if eth > 0 or usdc > 0:
            found_count += 1
            print(
                f"{agent_id:<22} | {str(owner_id):<15} | {wallet_addr:<42} | {format_token_amount(eth, 6):<10} | {format_token_amount(usdc, 2):<10}"
            )

    print("-" * 110)
    print(f"Total agents with > 0 balance: {found_count}")


if __name__ == "__main__":
    asyncio.run(main())
