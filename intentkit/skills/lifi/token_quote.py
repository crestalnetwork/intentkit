from typing import Any, Dict, List, Optional, Type

import httpx
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.lifi.base import LiFiBaseTool
from intentkit.skills.lifi.utils import (
    LIFI_API_URL,
    build_quote_params,
    format_duration,
    format_fees_and_gas,
    format_quote_basic_info,
    format_route_info,
    handle_api_response,
    validate_inputs,
)


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

    name: str = "lifi_token_quote"
    description: str = (
        "Get a quote for transferring tokens across blockchains or swapping tokens.\n"
        "Use this tool to check rates, fees, and estimated time for token transfers without executing them.\n"
        "Supports all major chains like Ethereum, Polygon, Arbitrum, Optimism, Base, and more."
    )
    args_schema: Type[BaseModel] = TokenQuoteInput
    api_url: str = LIFI_API_URL

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

            # Validate all inputs
            validation_error = validate_inputs(
                from_chain,
                to_chain,
                from_token,
                to_token,
                from_amount,
                slippage,
                self.allowed_chains,
            )
            if validation_error:
                return validation_error

            self.logger.info(
                f"Requesting LiFi quote: {from_amount} {from_token} on {from_chain} -> {to_token} on {to_chain}"
            )

            # Build API parameters
            api_params = build_quote_params(
                from_chain, to_chain, from_token, to_token, from_amount, slippage
            )

            # Make API request
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        f"{self.api_url}/quote",
                        params=api_params,
                        timeout=30.0,
                    )
                except httpx.TimeoutException:
                    return "Request timed out. The LiFi service might be temporarily unavailable. Please try again."
                except httpx.ConnectError:
                    return "Connection error. Unable to reach LiFi service. Please check your internet connection."
                except Exception as e:
                    self.logger.error("LiFi_API_Error: %s", str(e))
                    return f"Error making API request: {str(e)}"

                # Handle response
                data, error = handle_api_response(
                    response, from_token, from_chain, to_token, to_chain
                )
                if error:
                    self.logger.error("LiFi_API_Error: %s", error)
                    return error

                # Format the quote result
                return self._format_quote_result(data)

        except Exception as e:
            self.logger.error("LiFi_Error: %s", str(e))
            return f"An unexpected error occurred: {str(e)}"

    def _format_quote_result(self, data: Dict[str, Any]) -> str:
        """Format quote result into human-readable text."""
        try:
            # Get basic info
            info = format_quote_basic_info(data)

            # Build result string
            result = "### Token Transfer Quote\n\n"
            result += f"**From:** {info['from_amount']} {info['from_token']} on {info['from_chain']}\n"
            result += f"**To:** {info['to_amount']} {info['to_token']} on {info['to_chain']}\n"
            result += (
                f"**Minimum Received:** {info['to_amount_min']} {info['to_token']}\n"
            )
            result += f"**Bridge/Exchange:** {info['tool']}\n\n"

            # Add USD values if available
            if info["from_amount_usd"] and info["to_amount_usd"]:
                result += f"**Value:** ${info['from_amount_usd']} → ${info['to_amount_usd']}\n\n"

            # Add execution time estimate
            if info["execution_duration"]:
                time_str = format_duration(info["execution_duration"])
                result += f"**Estimated Time:** {time_str}\n\n"

            # Add fees and gas costs
            fees_text, gas_text = format_fees_and_gas(data)
            if fees_text:
                result += fees_text + "\n"
            if gas_text:
                result += gas_text + "\n"

            # Add route information
            route_text = format_route_info(data)
            if route_text:
                result += route_text + "\n"

            result += "---\n"
            result += (
                "*Use token_execute to perform this transfer with your CDP wallet*"
            )

            return result

        except Exception as e:
            self.logger.error("Format_Error: %s", str(e))
            return f"Quote received but formatting failed: {str(e)}\nRaw data: {str(data)[:500]}..."
