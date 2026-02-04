import asyncio
import logging
import os
import sys
from decimal import Decimal
from typing import Any

from cdp import parse_units
from sqlalchemy import select
from web3 import Web3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

USDC_DECIMALS = 6
DEFAULT_GAS_RESERVE_ETH = Decimal("0.00005")


def resolve_owner_address(user: Any) -> str | None:
    if user.evm_wallet_address and Web3.is_address(user.evm_wallet_address):
        return Web3.to_checksum_address(user.evm_wallet_address)
    if user.id and Web3.is_address(user.id):
        return Web3.to_checksum_address(user.id)
    return None


def compute_transferable_eth_wei(balance_wei: int, reserve_wei: int) -> int:
    if balance_wei <= reserve_wei:
        return 0
    return balance_wei - reserve_wei


def format_token_amount(amount: Decimal, decimals: int) -> str:
    text = f"{amount:.{decimals}f}"
    text = text.rstrip("0").rstrip(".")
    return text if text else "0"


def extract_tx_hash(result: Any) -> str:
    if isinstance(result, str):
        return result
    for attr in ("transaction_hash", "tx_hash", "hash", "user_op_hash"):
        if hasattr(result, attr):
            return str(getattr(result, attr))
    if isinstance(result, dict):
        for key in ("transaction_hash", "tx_hash", "hash", "user_op_hash"):
            if key in result:
                return str(result[key])
    return str(result)


async def transfer_usdc(
    account: Any,
    cdp_network: str,
    owner_address: str,
    wallet_address: str,
    network_id: str,
) -> tuple[str, str]:
    from intentkit.skills.erc20.constants import ERC20_ABI, TOKEN_ADDRESSES_BY_SYMBOLS
    from intentkit.wallets.web3 import get_web3_client

    token_address = TOKEN_ADDRESSES_BY_SYMBOLS.get(network_id, {}).get("USDC")
    if not token_address:
        return "0", "skip:no_usdc_address"

    web3_client = get_web3_client(network_id)
    contract = web3_client.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=ERC20_ABI,
    )
    balance = contract.functions.balanceOf(
        Web3.to_checksum_address(wallet_address)
    ).call()
    if not isinstance(balance, int) or balance <= 0:
        return "0", "skip:no_balance"

    amount_decimal = Decimal(balance) / Decimal(10**USDC_DECIMALS)
    amount_atomic = parse_units(
        format_token_amount(amount_decimal, USDC_DECIMALS), USDC_DECIMALS
    )
    result = await account.transfer(
        to=owner_address,
        amount=amount_atomic,
        token="usdc",
        network=cdp_network,
    )
    return format_token_amount(amount_decimal, USDC_DECIMALS), extract_tx_hash(result)


async def transfer_eth(
    account: Any,
    cdp_network: str,
    owner_address: str,
    wallet_address: str,
    network_id: str,
    gas_reserve_wei: int,
) -> tuple[str, str]:
    from intentkit.wallets.web3 import get_web3_client

    web3_client = get_web3_client(network_id)
    balance_wei = web3_client.eth.get_balance(Web3.to_checksum_address(wallet_address))
    transferable_wei = compute_transferable_eth_wei(balance_wei, gas_reserve_wei)
    if transferable_wei <= 0:
        return "0", "skip:no_balance"

    amount_decimal = Decimal(transferable_wei) / Decimal(10**18)
    result = await account.transfer(
        to=owner_address,
        amount=transferable_wei,
        token="eth",
        network=cdp_network,
    )
    return format_token_amount(amount_decimal, 18), extract_tx_hash(result)


async def process_agent(
    agent_row: Any,
    agent_data: Any | None,
    gas_reserve_wei: int,
) -> None:
    from intentkit.config.db import get_session
    from intentkit.models.agent import Agent
    from intentkit.models.user import UserTable
    from intentkit.wallets.cdp import get_cdp_client, get_cdp_network

    agent = Agent.model_validate(agent_row)
    if not agent.owner:
        logger.info(
            "%s %s USDC 0 tx=skip:no_owner",
            agent.id,
            agent_data.evm_wallet_address if agent_data else None,
        )
        logger.info(
            "%s %s ETH 0 tx=skip:no_owner",
            agent.id,
            agent_data.evm_wallet_address if agent_data else None,
        )
        return

    async with get_session() as session:
        user_row = await session.get(UserTable, agent.owner)
    if not user_row:
        logger.info(
            "%s %s USDC 0 tx=skip:owner_not_found",
            agent.id,
            agent_data.evm_wallet_address if agent_data else None,
        )
        logger.info(
            "%s %s ETH 0 tx=skip:owner_not_found",
            agent.id,
            agent_data.evm_wallet_address if agent_data else None,
        )
        return

    owner_address = resolve_owner_address(user_row)
    if not owner_address:
        logger.info(
            "%s %s USDC 0 tx=skip:owner_address_invalid",
            agent.id,
            agent_data.evm_wallet_address if agent_data else None,
        )
        logger.info(
            "%s %s ETH 0 tx=skip:owner_address_invalid",
            agent.id,
            agent_data.evm_wallet_address if agent_data else None,
        )
        return

    if not agent_data or not agent_data.evm_wallet_address:
        logger.info("%s None USDC 0 tx=skip:no_wallet", agent.id)
        logger.info("%s None ETH 0 tx=skip:no_wallet", agent.id)
        return

    wallet_address = agent_data.evm_wallet_address
    if owner_address.lower() == wallet_address.lower():
        logger.info(
            "%s %s USDC 0 tx=skip:owner_is_wallet",
            agent.id,
            wallet_address,
        )
        logger.info(
            "%s %s ETH 0 tx=skip:owner_is_wallet",
            agent.id,
            wallet_address,
        )
        return

    try:
        cdp_network = get_cdp_network(agent)
    except Exception as exc:
        logger.info(
            "%s %s USDC 0 tx=skip:bad_network:%s",
            agent.id,
            wallet_address,
            str(exc),
        )
        logger.info(
            "%s %s ETH 0 tx=skip:bad_network:%s",
            agent.id,
            wallet_address,
            str(exc),
        )
        return

    cdp_client = get_cdp_client()
    account = await cdp_client.evm.get_account(address=wallet_address)

    usdc_amount, usdc_tx = await transfer_usdc(
        account=account,
        cdp_network=cdp_network,
        owner_address=owner_address,
        wallet_address=wallet_address,
        network_id=str(agent.network_id),
    )
    logger.info(
        "%s %s USDC %s tx=%s",
        agent.id,
        wallet_address,
        usdc_amount,
        usdc_tx,
    )

    eth_amount, eth_tx = await transfer_eth(
        account=account,
        cdp_network=cdp_network,
        owner_address=owner_address,
        wallet_address=wallet_address,
        network_id=str(agent.network_id),
        gas_reserve_wei=gas_reserve_wei,
    )
    logger.info(
        "%s %s ETH %s tx=%s",
        agent.id,
        wallet_address,
        eth_amount,
        eth_tx,
    )


async def main() -> None:
    from intentkit.config.config import config
    from intentkit.config.db import get_session, init_db
    from intentkit.models.agent.db import AgentTable
    from intentkit.models.agent_data import AgentDataTable

    await init_db(**config.db)
    gas_reserve_wei = int(DEFAULT_GAS_RESERVE_ETH * Decimal(10**18))

    async with get_session() as session:
        result = await session.execute(
            select(AgentTable, AgentDataTable)
            .outerjoin(AgentDataTable, AgentDataTable.id == AgentTable.id)
            .where(AgentTable.wallet_provider == "cdp")
        )
        rows = result.all()

    for agent_row, agent_data in rows:
        await process_agent(agent_row, agent_data, gas_reserve_wei)


if __name__ == "__main__":
    asyncio.run(main())
