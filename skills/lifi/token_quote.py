from typing import Any, Dict, List, Optional, Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from skills.lifi.base import LiFiBaseTool


class TokenQuoteInput(BaseModel):
    """Input for the TokenQuote skill."""

    from_chain: str = Field(
        description="The source chain (e.g., 'ETH', 'POL', 'ARB', 'DAI'). Can be chain ID or chain key."
    )
    to_chain: str = Field(
        description="The destination chain (e.g., 'ETH', 'POL', 'ARB', 'DAI'). Can be chain ID or chain key."
    )
    from_token: str = Field(
        description="The token to send (e.g., 'USDC', 'ETH', 'DAI'). Can be token address or symbol."
    )
    to_token: str = Field(
        description="The token to receive (e.g., 'USDC', 'ETH', 'DAI'). Can be token address or symbol."
    )
    from_amount: str = Field(
        description="The amount to send, including all decimals (e.g., '1000000' for 1 USDC with 6 decimals)."
    )
    slippage: float = Field(
        default=0.03,
        description="The maximum allowed slippage for the transaction (0.03 represents 3%).",
    )


class TokenQuote(LiFiBaseTool):
    """Tool for getting token transfer quotes across chains using LiFi.

    This tool provides quotes for token transfers and swaps without executing transactions.
    """

    name: str = "token_quote"
    description: str = (
        "Get a quote for transferring tokens across blockchains or swapping tokens.\n"
        "Use this tool to check rates, fees, and estimated time for token transfers without executing them."
    )
    args_schema: Type[BaseModel] = TokenQuoteInput
    api_url: str = "https://li.quest/v1"

    # Configuration options
    default_slippage: float = 0.03
    allowed_chains: Optional[List[str]] = None

    def __init__(
        self,
        skill_store: SkillStoreABC,
        default_slippage: float = 0.03,
        allowed_chains: Optional[List[str]] = None,
    ):
        """Initialize the TokenQuote skill with configuration options."""
        super().__init__(skill_store=skill_store)
        self.default_slippage = default_slippage
        self.allowed_chains = allowed_chains

    async def _arun(
        self,
        config: RunnableConfig,
        from_chain: str,
        to_chain: str,
        from_token: str,
        to_token: str,
        from_amount: str,
        slippage: float = None,
        **kwargs,
    ) -> str:
        """Get a quote for token transfer."""
        try:
            # Use provided slippage or default
            if slippage is None:
                slippage = self.default_slippage

            # Validate chains if restricted
            if self.allowed_chains:
                if from_chain not in self.allowed_chains:
                    return f"Source chain '{from_chain}' is not allowed. Allowed chains: {', '.join(self.allowed_chains)}"
                if to_chain not in self.allowed_chains:
                    return f"Destination chain '{to_chain}' is not allowed. Allowed chains: {', '.join(self.allowed_chains)}"

            # Use dummy address for quotes
            from_address = "0x552008c0f6870c2f77e5cC1d2eb9bdff03e30Ea0"

            # Request quote from LiFi API
            api_params = {
                "fromChain": from_chain,
                "toChain": to_chain,
                "fromToken": from_token,
                "toToken": to_token,
                "fromAmount": from_amount,
                "fromAddress": from_address,
                "slippage": slippage,
            }

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        f"{self.api_url}/quote",
                        params=api_params,
                        timeout=30.0,
                    )
                except Exception as e:
                    self.logger.error("LiFi_API_Error: %s", str(e))
                    return f"Error making API request: {str(e)}"

                if response.status_code != 200:
                    self.logger.error("LiFi_API_Error: %s", response.text)
                    return (
                        f"Error getting quote: {response.status_code} - {response.text}"
                    )

                data = response.json()

                # Format the quote result for readable output
                result = self._format_quote_result(data)
                return result

        except Exception as e:
            self.logger.error("LiFi_Error: %s", str(e))
            return f"An error occurred: {str(e)}"

    def _format_quote_result(self, data: Dict[str, Any]) -> str:
        """Format quote result into human-readable text."""
        action = data.get("action", {})
        estimate = data.get("estimate", {})

        from_token_info = action.get("fromToken", {})
        to_token_info = action.get("toToken", {})

        from_chain_id = action.get("fromChainId")
        to_chain_id = action.get("toChainId")

        from_amount = action.get("fromAmount", "0")
        to_amount = estimate.get("toAmount", "0")
        to_amount_min = estimate.get("toAmountMin", "0")

        # Format amounts with appropriate decimals
        from_token_decimals = from_token_info.get("decimals", 18)
        to_token_decimals = to_token_info.get("decimals", 18)

        from_amount_formatted = self._format_amount(from_amount, from_token_decimals)
        to_amount_formatted = self._format_amount(to_amount, to_token_decimals)
        to_amount_min_formatted = self._format_amount(to_amount_min, to_token_decimals)

        # Extract gas and fee costs
        gas_costs = estimate.get("gasCosts", [])
        fee_costs = []

        # Collect fee information from included steps
        for step in data.get("includedSteps", []):
            step_fees = step.get("estimate", {}).get("feeCosts", [])
            if step_fees:
                fee_costs.extend(step_fees)

        # Build formatted result
        result = "### Transfer Quote\n\n"
        result += f"**From:** {from_amount_formatted} {from_token_info.get('symbol', 'Unknown')} on {self._get_chain_name(from_chain_id)}\n"
        result += f"**To:** {to_amount_formatted} {to_token_info.get('symbol', 'Unknown')} on {self._get_chain_name(to_chain_id)}\n"
        result += f"**Minimum Received:** {to_amount_min_formatted} {to_token_info.get('symbol', 'Unknown')}\n\n"

        # Add USD values if available
        if "fromAmountUSD" in estimate and "toAmountUSD" in estimate:
            result += f"**Value:** ${estimate.get('fromAmountUSD')} → ${estimate.get('toAmountUSD')}\n\n"

        # Add execution time estimate
        if "executionDuration" in estimate:
            duration = estimate.get("executionDuration")
            if duration < 60:
                time_str = f"{duration} seconds"
            else:
                time_str = f"{duration // 60} minutes {duration % 60} seconds"
            result += f"**Estimated Time:** {time_str}\n\n"

        # Add fee information
        if fee_costs:
            result += "**Fees:**\n"
            for fee in fee_costs:
                fee_name = fee.get("name", "Unknown fee")
                fee_amount = fee.get("amount", "0")
                fee_token = fee.get("token", {}).get("symbol", "")
                fee_decimals = fee.get("token", {}).get("decimals", 18)
                fee_percentage = fee.get("percentage", "0")

                fee_amount_formatted = self._format_amount(fee_amount, fee_decimals)
                result += f"- {fee_name}: {fee_amount_formatted} {fee_token} ({float(fee_percentage) * 100:.2f}%)\n"

            result += "\n"

        # Add gas costs
        if gas_costs:
            result += "**Gas Cost:**\n"
            for gas in gas_costs:
                gas_amount = gas.get("amount", "0")
                gas_token = gas.get("token", {}).get("symbol", "")
                gas_decimals = gas.get("token", {}).get("decimals", 18)
                gas_amount_usd = gas.get("amountUSD", "")

                gas_amount_formatted = self._format_amount(gas_amount, gas_decimals)
                if gas_amount_usd:
                    result += (
                        f"- {gas_amount_formatted} {gas_token} (${gas_amount_usd})\n"
                    )
                else:
                    result += f"- {gas_amount_formatted} {gas_token}\n"

        # Add route information
        if data.get("includedSteps"):
            result += "\n**Route:**\n"
            for i, step in enumerate(data.get("includedSteps", [])):
                tool = step.get("toolDetails", {}).get(
                    "name", step.get("tool", "Unknown")
                )
                from_token_symbol = step.get("fromToken", {}).get("symbol", "Unknown")
                to_token_symbol = step.get("toToken", {}).get("symbol", "Unknown")

                if i == 0:
                    result += f"1. {tool}: {from_token_symbol} → {to_token_symbol}\n"
                else:
                    result += (
                        f"{i + 1}. {tool}: {from_token_symbol} → {to_token_symbol}\n"
                    )

        return result

    def _format_amount(self, amount: str, decimals: int) -> str:
        """Format token amount with appropriate decimal places."""
        try:
            # Convert to decimal representation
            amount_float = float(amount) / (10**decimals)

            # Use different precision based on amount size
            if amount_float >= 1:
                return f"{amount_float:.3f}"
            elif amount_float >= 0.0001:
                return f"{amount_float:.6f}"
            else:
                return f"{amount_float:.8f}"
        except (ValueError, TypeError):
            return amount

    def _get_chain_name(self, chain_id: int) -> str:
        """Convert chain ID to human-readable name."""
        chain_names = {
            1: "Ethereum",
            10: "Optimism",
            56: "BNB Chain",
            100: "Gnosis Chain",
            137: "Polygon",
            42161: "Arbitrum",
            43114: "Avalanche",
        }
        return chain_names.get(chain_id, f"Chain {chain_id}")
