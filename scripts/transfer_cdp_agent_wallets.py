import asyncio
import logging
import os
import sys
from decimal import Decimal
from typing import Any

from cdp import parse_units
from cdp.openapi_client.errors import ApiError
from sqlalchemy import select
from web3 import Web3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

USDC_DECIMALS = 6
DEFAULT_GAS_RESERVE_ETH = Decimal("0.00001")


def resolve_owner_address(user: Any) -> str | None:
    def _is_valid(addr: str | None) -> str | None:
        if not addr:
            return None
        addr = addr.strip()
        if not addr.startswith("0x"):
            addr = f"0x{addr}"
        if Web3.is_address(addr):
            return Web3.to_checksum_address(addr)
        return None

    # Check evm_wallet_address first
    addr = _is_valid(user.evm_wallet_address)
    if addr:
        return addr

    # Fallback to user id as address
    addr = _is_valid(user.id)
    if addr:
        return addr

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
    try:
        result = await account.transfer(
            to=owner_address,
            amount=amount_atomic,
            token="usdc",
            network=cdp_network,
        )
    except ApiError as e:
        if "Insufficient balance" in str(e) or e.http_code == 400:
            return "0", "skip:insufficient_balance"
        raise
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
    try:
        result = await account.transfer(
            to=owner_address,
            amount=transferable_wei,
            token="eth",
            network=cdp_network,
        )
    except ApiError as e:
        if "Insufficient balance" in str(e) or e.http_code == 400:
            return "0", "skip:insufficient_balance"
        raise
    return format_token_amount(amount_decimal, 18), extract_tx_hash(result)


async def process_agent(
    agent_row: Any,
    agent_data: Any | None,
    gas_reserve_wei: int,
) -> tuple[str, str]:
    from intentkit.config.db import get_session
    from intentkit.models.agent import Agent
    from intentkit.models.user import UserTable
    from intentkit.wallets.cdp import get_cdp_client, get_cdp_network

    agent = Agent.model_validate(agent_row)
    if not agent.owner:
        return "skip:no_owner", "skip:no_owner"

    async with get_session() as session:
        user_row = await session.get(UserTable, agent.owner)
    if not user_row:
        return "skip:owner_not_found", "skip:owner_not_found"

    owner_address = resolve_owner_address(user_row)
    if not owner_address:
        return "skip:owner_address_invalid", "skip:owner_address_invalid"

    if not agent_data or not agent_data.evm_wallet_address:
        return "skip:no_wallet", "skip:no_wallet"

    wallet_address = agent_data.evm_wallet_address
    if owner_address.lower() == wallet_address.lower():
        return "skip:owner_is_wallet", "skip:owner_is_wallet"

    try:
        cdp_network = get_cdp_network(agent)
    except Exception as exc:
        return f"skip:bad_network:{exc}", f"skip:bad_network:{exc}"

    cdp_client = get_cdp_client()
    try:
        account = await cdp_client.evm.get_account(address=wallet_address)
    except ApiError as e:
        if e.http_code == 404:
            return "skip:cdp_account_not_found", "skip:cdp_account_not_found"
        raise

    usdc_amount, usdc_tx = await transfer_usdc(
        account=account,
        cdp_network=cdp_network,
        owner_address=owner_address,
        wallet_address=wallet_address,
        network_id=str(agent.network_id),
    )
    # Only log if there was actual balance (not skip:no_balance)
    if usdc_tx != "skip:no_balance" and usdc_tx != "skip:no_usdc_address":
        if usdc_tx.startswith("skip:"):
            logger.info(
                "%s %s USDC %s tx=%s (failed)",
                agent.id,
                wallet_address,
                usdc_amount,
                usdc_tx,
            )
        else:
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
    # Only log if there was actual balance (not skip:no_balance)
    if eth_tx != "skip:no_balance":
        if eth_tx.startswith("skip:"):
            logger.info(
                "%s %s ETH %s tx=%s (failed)",
                agent.id,
                wallet_address,
                eth_amount,
                eth_tx,
            )
        else:
            logger.info(
                "%s %s ETH %s tx=%s",
                agent.id,
                wallet_address,
                eth_amount,
                eth_tx,
            )
    return usdc_tx, eth_tx


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

    total_agents = 0
    usdc_success = 0
    usdc_skipped = 0
    eth_success = 0
    eth_skipped = 0

    # Track reasons for skipping
    usdc_skip_reasons = {}
    eth_skip_reasons = {}

    for agent_row, agent_data in rows:
        total_agents += 1
        usdc_tx, eth_tx = await process_agent(agent_row, agent_data, gas_reserve_wei)

        if usdc_tx.startswith("skip:"):
            usdc_skipped += 1
            reason = usdc_tx
            usdc_skip_reasons[reason] = usdc_skip_reasons.get(reason, 0) + 1
        else:
            usdc_success += 1

        if eth_tx.startswith("skip:"):
            eth_skipped += 1
            reason = eth_tx
            eth_skip_reasons[reason] = eth_skip_reasons.get(reason, 0) + 1
        else:
            eth_success += 1

    logger.info("=" * 40)
    logger.info("Transfer Summary")
    logger.info("=" * 40)
    logger.info("Total Agents Processed : %d", total_agents)
    logger.info("-" * 40)
    logger.info("USDC Transfers Success : %d", usdc_success)
    logger.info("USDC Transfers Skipped : %d", usdc_skipped)
    logger.info("-" * 40)
    logger.info("ETH Transfers Success  : %d", eth_success)
    logger.info("ETH Transfers Skipped  : %d", eth_skipped)
    logger.info("=" * 40)

    if usdc_skip_reasons:
        logger.info("USDC Skip Reasons:")
        for reason, count in usdc_skip_reasons.items():
            logger.info("  %s: %d", reason, count)

    if eth_skip_reasons:
        logger.info("-" * 40)
        logger.info("ETH Skip Reasons:")
        for reason, count in eth_skip_reasons.items():
            logger.info("  %s: %d", reason, count)

    logger.info("=" * 40)


if __name__ == "__main__":
    asyncio.run(main())
