"""PancakeSwap V3 add liquidity skill — mint a new liquidity position."""

import time
from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.pancakeswap.base import PancakeSwapBaseTool
from intentkit.skills.pancakeswap.constants import (
    FACTORY_ABI,
    FACTORY_ADDRESS,
    MASTERCHEF_V3_ADDRESSES,
    MAX_TICK,
    MIN_TICK,
    NETWORK_TO_CHAIN_ID,
    POSITION_MANAGER_ABI,
    POSITION_MANAGER_ADDRESS,
    TICK_SPACINGS,
    WRAPPED_NATIVE_ADDRESSES,
)
from intentkit.skills.pancakeswap.utils import (
    convert_amount,
    ensure_allowance,
    get_decimals,
    get_token_symbol,
    resolve_token,
)

NAME = "pancakeswap_add_liquidity"


class PancakeSwapAddLiquidityInput(BaseModel):
    """Input for PancakeSwap add liquidity."""

    token_a: str = Field(
        description="First token address, or 'native' for native token"
    )
    token_b: str = Field(
        description="Second token address, or 'native' for native token"
    )
    amount_a: str = Field(
        description="Amount of first token in human-readable format (e.g. '1.5')"
    )
    amount_b: str = Field(
        description="Amount of second token in human-readable format (e.g. '1.5')"
    )
    fee_tier: int = Field(
        default=2500,
        description="Fee tier: 100 (0.01%), 500 (0.05%), 2500 (0.25%), 10000 (1%)",
    )
    slippage: float = Field(
        default=0.5,
        description="Slippage tolerance in percent (e.g. 0.5 for 0.5%)",
    )


class PancakeSwapAddLiquidity(PancakeSwapBaseTool):
    """Add liquidity to a PancakeSwap V3 pool."""

    name: str = NAME
    description: str = (
        "Add liquidity to a PancakeSwap V3 pool. Creates a full-range position. "
        "Auto-stakes into MasterChef V3 farm if eligible for CAKE rewards. "
        "Provide token addresses and amounts in human-readable format."
    )
    args_schema: ArgsSchema | None = PancakeSwapAddLiquidityInput

    @override
    async def _arun(
        self,
        token_a: str,
        token_b: str,
        amount_a: str,
        amount_b: str,
        fee_tier: int = 2500,
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
                    f"PancakeSwap not supported on {network_id}. "
                    f"Supported: {', '.join(NETWORK_TO_CHAIN_ID.keys())}"
                )

            tick_spacing = TICK_SPACINGS.get(fee_tier)
            if not tick_spacing:
                raise ToolException(
                    f"Invalid fee tier {fee_tier}. Valid: 100, 500, 2500, 10000"
                )

            wallet = await self.get_unified_wallet()
            w3 = self.web3_client()

            # Resolve tokens (V3 uses wrapped tokens)
            is_native_a = token_a.lower() == "native"
            is_native_b = token_b.lower() == "native"
            addr_a = resolve_token(token_a, chain_id)
            addr_b = resolve_token(token_b, chain_id)

            # Get decimals
            dec_a = await get_decimals(w3, addr_a, chain_id)
            dec_b = await get_decimals(w3, addr_b, chain_id)

            # Convert amounts
            raw_a = convert_amount(amount_a, dec_a)
            raw_b = convert_amount(amount_b, dec_b)

            # Sort tokens: V3 requires token0 < token1 by address
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

            # Validate pool exists
            factory = w3.eth.contract(
                address=Web3.to_checksum_address(FACTORY_ADDRESS),
                abi=FACTORY_ABI,
            )
            pool_address = await factory.functions.getPool(
                token0, token1, fee_tier
            ).call()
            if pool_address == "0x0000000000000000000000000000000000000000":
                raise ToolException(
                    f"No pool exists for this pair with fee tier {fee_tier}"
                )

            # Handle native tokens: wrap by sending to WETH/WBNB contract
            wrapped_addr = WRAPPED_NATIVE_ADDRESSES.get(chain_id)
            if (is_native0 or is_native1) and wrapped_addr:
                native_amount = amount0 if is_native0 else amount1
                weth_abi = [
                    {
                        "inputs": [],
                        "name": "deposit",
                        "outputs": [],
                        "stateMutability": "payable",
                        "type": "function",
                    }
                ]
                weth = w3.eth.contract(
                    address=Web3.to_checksum_address(wrapped_addr),
                    abi=weth_abi,
                )
                deposit_data = weth.encode_abi("deposit", [])
                tx_hash = await wallet.send_transaction(
                    to=Web3.to_checksum_address(wrapped_addr),
                    data=deposit_data,
                    value=native_amount,
                )
                await wallet.wait_for_receipt(tx_hash)

            # Calculate full-range tick bounds
            tick_lower = (MIN_TICK // tick_spacing) * tick_spacing
            tick_upper = (MAX_TICK // tick_spacing) * tick_spacing

            # Calculate minimum amounts with slippage
            slippage_factor = Decimal(1) - Decimal(str(slippage)) / Decimal(100)
            amount0_min = int(Decimal(amount0) * slippage_factor)
            amount1_min = int(Decimal(amount1) * slippage_factor)

            # Approve both tokens to PositionManager
            pm_address = Web3.to_checksum_address(POSITION_MANAGER_ADDRESS)
            await ensure_allowance(w3, wallet, token0, pm_address, amount0)
            await ensure_allowance(w3, wallet, token1, pm_address, amount1)

            # Build mint calldata
            pm = w3.eth.contract(address=pm_address, abi=POSITION_MANAGER_ABI)
            wallet_address = Web3.to_checksum_address(wallet.address)
            deadline = int(time.time()) + 600  # 10 minutes

            mint_data = pm.encode_abi(
                "mint",
                [
                    (
                        token0,
                        token1,
                        fee_tier,
                        tick_lower,
                        tick_upper,
                        amount0,
                        amount1,
                        amount0_min,
                        amount1_min,
                        wallet_address,
                        deadline,
                    )
                ],
            )

            tx_hash = await wallet.send_transaction(
                to=pm_address,
                data=mint_data,
            )
            receipt = await wallet.wait_for_receipt(tx_hash)
            status = receipt.get("status", 0)
            if status != 1:
                raise ToolException(f"Mint transaction failed. Hash: {tx_hash}")

            # Extract tokenId from Transfer event logs
            token_id = _extract_token_id(receipt)

            # Auto-stake into MasterChef V3
            farming_status = "Not staked (no farm on this chain)"
            masterchef_addr = MASTERCHEF_V3_ADDRESSES.get(chain_id)
            if masterchef_addr and token_id:
                farming_status = await self._try_auto_stake(
                    wallet, pm, token_id, masterchef_addr, wallet_address
                )

            # Format result
            sym0 = await get_token_symbol(w3, token0, chain_id)
            sym1 = await get_token_symbol(w3, token1, chain_id)
            fee_pct = Decimal(fee_tier) / Decimal(10000)
            dep0 = Decimal(amount0) / Decimal(10**dec0)
            dep1 = Decimal(amount1) / Decimal(10**dec1)

            return (
                f"**Liquidity Added**\n"
                f"Position ID: {token_id}\n"
                f"Pool: {sym0}/{sym1} ({fee_pct}%)\n"
                f"Deposited: {dep0:.8f} {sym0}, {dep1:.8f} {sym1}\n"
                f"Range: Full range [{tick_lower}, {tick_upper}]\n"
                f"Farming: {farming_status}\n"
                f"Tx: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Add liquidity failed: {e!s}")

    async def _try_auto_stake(
        self,
        wallet: Any,
        pm: Any,
        token_id: int,
        masterchef_addr: str,
        wallet_address: str,
    ) -> str:
        """Try to auto-stake position into MasterChef V3 farm."""
        try:
            checksum_mc = Web3.to_checksum_address(masterchef_addr)
            # safeTransferFrom(wallet, masterchef, tokenId)
            transfer_data = pm.encode_abi(
                "safeTransferFrom",
                [wallet_address, checksum_mc, token_id],
            )
            tx_hash = await wallet.send_transaction(
                to=Web3.to_checksum_address(POSITION_MANAGER_ADDRESS),
                data=transfer_data,
            )
            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException("Not staked (farm transaction failed)")

            # Persist staked token ID
            staked_data = await self.get_agent_skill_data("staked_token_ids")
            token_ids: list[int] = (
                staked_data.get("token_ids", []) if staked_data else []
            )
            token_ids.append(token_id)
            await self.save_agent_skill_data(
                "staked_token_ids", {"token_ids": token_ids}
            )

            return "Staked in MasterChef V3 farm"
        except ToolException:
            raise
        except Exception:
            raise ToolException("Not staked (pool not eligible for farming)")


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
