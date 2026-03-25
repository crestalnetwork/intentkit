"""Aerodrome Slipstream add liquidity skill — mint a new CL position."""

import time
from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.aerodrome.base import AerodromeBaseTool
from intentkit.skills.aerodrome.constants import (
    CL_FACTORY_ABI,
    CL_FACTORY_ADDRESS,
    CL_GAUGE_ABI,
    MAX_TICK,
    MIN_TICK,
    NETWORK_TO_CHAIN_ID,
    POSITION_MANAGER_ABI,
    POSITION_MANAGER_ADDRESS,
    SKILL_DATA_NAMESPACE,
    STAKED_DATA_KEY,
    TICK_SPACINGS,
    VOTER_ABI,
    VOTER_ADDRESS,
    WETH_DEPOSIT_ABI,
    WRAPPED_NATIVE_ADDRESS,
)
from intentkit.skills.aerodrome.utils import (
    convert_amount,
    ensure_allowance,
    get_decimals,
    get_token_symbol,
    resolve_token,
)

NAME = "aerodrome_add_liquidity"


class AerodromeAddLiquidityInput(BaseModel):
    """Input for Aerodrome add liquidity."""

    token_a: str = Field(description="First token address, or 'native' for ETH on Base")
    token_b: str = Field(
        description="Second token address, or 'native' for ETH on Base"
    )
    amount_a: str = Field(
        description="Amount of first token in human-readable format (e.g. '1.5')"
    )
    amount_b: str = Field(
        description="Amount of second token in human-readable format (e.g. '1.5')"
    )
    tick_spacing: int = Field(
        default=100,
        description="Tick spacing: 1 (stable), 50 (medium), 100 (standard), 200 (volatile)",
    )
    slippage: float = Field(
        default=0.5,
        description="Slippage tolerance in percent (e.g. 0.5 for 0.5%)",
    )


class AerodromeAddLiquidity(AerodromeBaseTool):
    """Add liquidity to an Aerodrome Slipstream pool on Base."""

    name: str = NAME
    description: str = (
        "Add liquidity to an Aerodrome Slipstream pool on Base. "
        "Creates a full-range CL position. "
        "Auto-stakes into gauge for AERO rewards if eligible. "
        "Provide token addresses and amounts in human-readable format."
    )
    args_schema: ArgsSchema | None = AerodromeAddLiquidityInput

    @override
    async def _arun(
        self,
        token_a: str,
        token_b: str,
        amount_a: str,
        amount_b: str,
        tick_spacing: int = 100,
        slippage: float = 0.5,
        **kwargs: Any,
    ) -> str:
        try:
            network_id = self.get_agent_network_id()
            if not network_id:
                raise ToolException("Agent network_id is not configured")

            chain_id = NETWORK_TO_CHAIN_ID.get(network_id)
            if not chain_id:
                raise ToolException(
                    f"Aerodrome is only supported on Base. "
                    f"Current network: {network_id}"
                )

            if tick_spacing not in TICK_SPACINGS:
                valid = ", ".join(str(t) for t in TICK_SPACINGS)
                raise ToolException(
                    f"Invalid tick spacing {tick_spacing}. Valid: {valid}"
                )

            wallet = await self.get_unified_wallet()
            w3 = self.web3_client()

            is_native_a = token_a.lower() == "native"
            is_native_b = token_b.lower() == "native"
            addr_a = resolve_token(token_a)
            addr_b = resolve_token(token_b)

            dec_a = await get_decimals(w3, addr_a)
            dec_b = await get_decimals(w3, addr_b)

            raw_a = convert_amount(amount_a, dec_a)
            raw_b = convert_amount(amount_b, dec_b)

            # CL requires token0 < token1 by address
            checksum_a = Web3.to_checksum_address(addr_a)
            checksum_b = Web3.to_checksum_address(addr_b)

            if int(checksum_a, 16) < int(checksum_b, 16):
                token0, token1 = checksum_a, checksum_b
                amount0, amount1 = raw_a, raw_b
                dec0, dec1 = dec_a, dec_b
                is_native0, is_native1 = is_native_a, is_native_b
            else:
                token0, token1 = checksum_b, checksum_a
                amount0, amount1 = raw_b, raw_a
                dec0, dec1 = dec_b, dec_a
                is_native0, is_native1 = is_native_b, is_native_a

            factory = w3.eth.contract(
                address=Web3.to_checksum_address(CL_FACTORY_ADDRESS),
                abi=CL_FACTORY_ABI,
            )
            pool_address = await factory.functions.getPool(
                token0, token1, tick_spacing
            ).call()
            if pool_address == "0x0000000000000000000000000000000000000000":
                raise ToolException(
                    f"No pool exists for this pair with tick spacing {tick_spacing}"
                )

            # Look up gauge before minting to fail fast without spending gas
            gauge_address = await self._lookup_gauge(w3, pool_address)

            if is_native0 or is_native1:
                native_amount = amount0 if is_native0 else amount1
                weth = w3.eth.contract(
                    address=Web3.to_checksum_address(WRAPPED_NATIVE_ADDRESS),
                    abi=WETH_DEPOSIT_ABI,
                )
                deposit_data = weth.encode_abi("deposit", [])
                tx_hash = await wallet.send_transaction(
                    to=Web3.to_checksum_address(WRAPPED_NATIVE_ADDRESS),
                    data=deposit_data,
                    value=native_amount,
                )
                await wallet.wait_for_receipt(tx_hash)

            tick_lower = -((-MIN_TICK) // tick_spacing) * tick_spacing
            tick_upper = (MAX_TICK // tick_spacing) * tick_spacing

            slippage_factor = Decimal(1) - Decimal(str(slippage)) / Decimal(100)
            amount0_min = int(Decimal(amount0) * slippage_factor)
            amount1_min = int(Decimal(amount1) * slippage_factor)

            checksum_pm = Web3.to_checksum_address(POSITION_MANAGER_ADDRESS)
            await ensure_allowance(w3, wallet, token0, checksum_pm, amount0)
            await ensure_allowance(w3, wallet, token1, checksum_pm, amount1)

            pm = w3.eth.contract(address=checksum_pm, abi=POSITION_MANAGER_ABI)
            wallet_address = Web3.to_checksum_address(wallet.address)
            deadline = int(time.time()) + 600  # 10 minutes

            mint_data = pm.encode_abi(
                "mint",
                [
                    (
                        token0,
                        token1,
                        tick_spacing,
                        tick_lower,
                        tick_upper,
                        amount0,
                        amount1,
                        amount0_min,
                        amount1_min,
                        wallet_address,
                        deadline,
                        0,  # sqrtPriceX96 = 0 (pool already exists)
                    )
                ],
            )

            tx_hash = await wallet.send_transaction(
                to=checksum_pm,
                data=mint_data,
            )
            receipt = await wallet.wait_for_receipt(tx_hash)
            status = receipt.get("status", 0)
            if status != 1:
                raise ToolException(f"Mint transaction failed. Hash: {tx_hash}")

            # Extract tokenId from Transfer event logs
            token_id = _extract_token_id(receipt)

            farming_status = "Not staked (no gauge found)"
            if token_id and gauge_address:
                farming_status = await self._try_auto_stake(
                    wallet, w3, pm, token_id, gauge_address
                )

            sym0 = await get_token_symbol(w3, token0)
            sym1 = await get_token_symbol(w3, token1)
            dep0 = Decimal(amount0) / Decimal(10**dec0)
            dep1 = Decimal(amount1) / Decimal(10**dec1)

            return (
                f"**Liquidity Added**\n"
                f"Position ID: {token_id}\n"
                f"Pool: {sym0}/{sym1} (tick spacing: {tick_spacing})\n"
                f"Deposited: {dep0:.8f} {sym0}, {dep1:.8f} {sym1}\n"
                f"Range: Full range [{tick_lower}, {tick_upper}]\n"
                f"Farming: {farming_status}\n"
                f"Tx: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Add liquidity failed: {e!s}")

    async def _lookup_gauge(self, w3: Any, pool_address: str) -> str | None:
        """Look up gauge address for a pool. Returns None if no gauge exists."""
        try:
            voter = w3.eth.contract(
                address=Web3.to_checksum_address(VOTER_ADDRESS),
                abi=VOTER_ABI,
            )
            gauge_address = await voter.functions.gauges(
                Web3.to_checksum_address(pool_address)
            ).call()
            if gauge_address == "0x0000000000000000000000000000000000000000":
                return None
            return gauge_address
        except Exception:
            return None

    async def _try_auto_stake(
        self,
        wallet: Any,
        w3: Any,
        pm: Any,
        token_id: int,
        gauge_address: str,
    ) -> str:
        """Auto-stake position into gauge for AERO rewards."""
        try:
            checksum_gauge = Web3.to_checksum_address(gauge_address)

            approve_data = pm.encode_abi("approve", [checksum_gauge, token_id])
            tx_hash = await wallet.send_transaction(
                to=Web3.to_checksum_address(POSITION_MANAGER_ADDRESS),
                data=approve_data,
            )
            await wallet.wait_for_receipt(tx_hash)

            # Deposit into gauge
            gauge = w3.eth.contract(address=checksum_gauge, abi=CL_GAUGE_ABI)
            deposit_data = gauge.encode_abi("deposit", [token_id])
            tx_hash = await wallet.send_transaction(
                to=checksum_gauge,
                data=deposit_data,
            )
            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                return "Not staked (gauge deposit failed)"

            # Use shared namespace so get_positions and remove_liquidity can read
            staked_data = await self.get_agent_skill_data_raw(
                SKILL_DATA_NAMESPACE, STAKED_DATA_KEY
            )
            token_ids: list[int] = (
                staked_data.get("token_ids", []) if staked_data else []
            )
            gauges: dict[str, str] = (
                staked_data.get("gauges", {}) if staked_data else {}
            )
            token_ids.append(token_id)
            gauges[str(token_id)] = gauge_address
            await self.save_agent_skill_data_raw(
                SKILL_DATA_NAMESPACE,
                STAKED_DATA_KEY,
                {"token_ids": token_ids, "gauges": gauges},
            )

            return "Staked in gauge for AERO rewards"
        except Exception:
            return "Not staked (pool not eligible for gauge)"


def _to_hex(value: Any) -> str:
    """Normalize a topic value to a lowercase hex string without 0x prefix."""
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, str):
        return value.lower().removeprefix("0x")
    if hasattr(value, "hex"):
        return value.hex().lower().removeprefix("0x")
    return ""


def _extract_token_id(receipt: dict[str, Any]) -> int | None:
    """Extract tokenId from mint receipt Transfer event logs."""
    transfer_topic = _to_hex(Web3.keccak(text="Transfer(address,address,uint256)"))
    zero_addr = "0" * 64

    for log in receipt.get("logs", []):
        topics = log.get("topics", [])
        if len(topics) >= 4:
            topic0 = _to_hex(topics[0])
            from_addr = _to_hex(topics[1])

            if topic0 == transfer_topic and from_addr == zero_addr:
                token_id_hex = _to_hex(topics[3])
                if token_id_hex:
                    return int(token_id_hex, 16)

    return None
