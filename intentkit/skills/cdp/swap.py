from typing import Optional, Type, Union

from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.clients import get_cdp_client
from intentkit.skills.cdp.base import CDPBaseTool


class SwapInput(BaseModel):
    """Input for Swap tool."""

    from_token: str = Field(
        description="The contract address of the token to swap from (e.g., '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913' for USDC on Base)"
    )
    to_token: str = Field(
        description="The contract address of the token to swap to (e.g., '0x4200000000000000000000000000000000000006' for WETH on Base)"
    )
    from_amount: Union[str, int] = Field(
        description="The amount to swap from in smallest unit (e.g., 1000000 for 1 USDC with 6 decimals)"
    )
    slippage_bps: Optional[int] = Field(
        default=100,
        description="Maximum slippage in basis points (100 = 1%). Defaults to 100 (1%)",
    )


class Swap(CDPBaseTool):
    """Tool for swapping tokens using CDP wallet.

    This tool uses the CDP API to execute token swaps on supported networks.
    It wraps the swap functionality from the EVM account.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    agent_id: str
    skill_store: SkillStoreABC

    name: str = "cdp_swap"
    description: str = (
        "This tool will swap tokens using the CDP wallet. "
        "It supports swapping between any ERC-20 tokens on supported networks (Base and Ethereum). "
        "You need to provide the contract addresses of both tokens and the amount to swap. "
        "The amount should be in the smallest unit of the token (e.g., wei for ETH, or atomic units for ERC-20 tokens). "
        "Common token addresses on Base: USDC=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913, WETH=0x4200000000000000000000000000000000000006. "
        "The tool will automatically handle gas estimation and transaction submission."
    )
    args_schema: Type[BaseModel] = SwapInput

    async def _arun(
        self,
        from_token: str,
        to_token: str,
        from_amount: Union[str, int],
        slippage_bps: Optional[int] = 100,
    ) -> str:
        """Async implementation of the tool to swap tokens.

        Args:
            from_token (str): The contract address of the token to swap from.
            to_token (str): The contract address of the token to swap to.
            from_amount (Union[str, int]): The amount to swap from in smallest unit.
            slippage_bps (Optional[int]): Maximum slippage in basis points. Defaults to 100 (1%).

        Returns:
            str: A message containing the swap result or error message.
        """
        try:
            # Get CDP client and network information
            cdp_client = await get_cdp_client(self.agent_id, self.skill_store)
            provider = await cdp_client.get_wallet_provider()
            provider_config = await cdp_client.get_provider_config()
            network_id = provider_config.network_id

            # Map network_id to the format expected by the swap API
            network_mapping = {
                "base-mainnet": "base",
                "ethereum-mainnet": "ethereum",
            }
            api_network = network_mapping.get(network_id, network_id)

            # Validate network is supported
            supported_networks = ["base", "ethereum"]
            if api_network not in supported_networks:
                return f"Error: Network {api_network} is not supported for swaps. Supported networks: {', '.join(supported_networks)}"

            # Get the EVM account
            client = provider.get_client()
            async with client:
                account = await client.evm.get_account(provider.get_address())

                # Import AccountSwapOptions here to avoid circular imports
                from cdp.actions.evm.swap.types import AccountSwapOptions

                # Create swap options
                swap_options = AccountSwapOptions(
                    network=api_network,
                    from_token=from_token,
                    to_token=to_token,
                    from_amount=str(from_amount),
                    slippage_bps=slippage_bps,
                )

                # Execute the swap
                result = await account.swap(swap_options)

                return (
                    f"Swap executed successfully!\n"
                    f"Transaction hash: {result.transaction_hash}\n"
                    f"Swapped from {from_token} to {to_token}\n"
                    f"Amount: {from_amount} (smallest units)\n"
                    f"Network: {api_network}\n"
                    f"Slippage tolerance: {slippage_bps} basis points ({slippage_bps / 100 if slippage_bps else 0}%)"
                )

        except Exception as e:
            return f"Error executing swap: {e!s}"
