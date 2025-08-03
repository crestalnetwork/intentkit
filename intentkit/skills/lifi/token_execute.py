import asyncio
from typing import Any, Dict, List, Optional, Type

import httpx
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.clients import get_cdp_client
from intentkit.skills.lifi.base import LiFiBaseTool
from intentkit.skills.lifi.token_quote import TokenQuote
from intentkit.skills.lifi.utils import (
    ERC20_ABI,
    LIFI_API_URL,
    build_quote_params,
    convert_chain_to_id,
    create_erc20_approve_data,
    format_amount,
    format_transaction_result,
    handle_api_response,
    is_native_token,
    prepare_transaction_params,
    validate_inputs,
)


class TokenExecuteInput(BaseModel):
    """Input for the TokenExecute skill."""

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
        description="Maximum acceptable slippage as a decimal (e.g., 0.03 for 3%). Default is 3%.",
    )


class TokenExecute(LiFiBaseTool):
    """Tool for executing token transfers across chains using LiFi.

    This tool executes actual token transfers and swaps using the CDP wallet provider.
    Requires a properly configured CDP wallet to work.
    """

    name: str = "lifi_token_execute"
    description: str = (
        "Execute a token transfer across blockchains or swap tokens on the same chain.\n"
        "This requires a CDP wallet with sufficient funds and proper network configuration.\n"
        "Use token_quote first to check rates and fees before executing.\n"
        "Supports all major chains like Ethereum, Polygon, Arbitrum, Optimism, Base, and more."
    )
    args_schema: Type[BaseModel] = TokenExecuteInput
    api_url: str = LIFI_API_URL

    # Configuration options
    default_slippage: float = 0.03
    allowed_chains: Optional[List[str]] = None
    max_execution_time: int = 300
    quote_tool: TokenQuote = Field(default=None, exclude=True)

    def __init__(
        self,
        skill_store: SkillStoreABC,
        default_slippage: float = 0.03,
        allowed_chains: Optional[List[str]] = None,
        max_execution_time: int = 300,
    ):
        """Initialize the TokenExecute skill with configuration options."""
        super().__init__(skill_store=skill_store)
        self.default_slippage = default_slippage
        self.allowed_chains = allowed_chains
        self.max_execution_time = max_execution_time
        # Initialize quote tool if not set
        if not self.quote_tool:
            self.quote_tool = TokenQuote(
                skill_store=skill_store,
                default_slippage=default_slippage,
                allowed_chains=allowed_chains,
            )

    def _format_quote_result(self, data: Dict[str, Any]) -> str:
        """Format the quote result in a readable format."""
        # Use the same formatting as token_quote
        return self.quote_tool._format_quote_result(data)

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
        """Execute a token transfer."""
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

            # Get agent context for CDP wallet
            context = self.get_context()
            agent_id = context.agent_id

            self.logger.info(
                f"Executing LiFi transfer: {from_amount} {from_token} on {from_chain} -> {to_token} on {to_chain}"
            )

            # Get CDP wallet provider
            cdp_wallet_provider = await self._get_cdp_wallet_provider(agent_id)
            if isinstance(cdp_wallet_provider, str):  # Error message
                return cdp_wallet_provider

            # Get wallet address
            from_address = cdp_wallet_provider.get_address()
            if not from_address:
                return "No wallet address available. Please check your CDP wallet configuration."

            # Get quote and execute transfer
            async with httpx.AsyncClient() as client:
                # Step 1: Get quote
                quote_data = await self._get_quote(
                    client,
                    from_chain,
                    to_chain,
                    from_token,
                    to_token,
                    from_amount,
                    slippage,
                    from_address,
                )
                if isinstance(quote_data, str):  # Error message
                    return quote_data

                # Step 2: Handle token approval if needed
                approval_result = await self._handle_token_approval(
                    cdp_wallet_provider, quote_data
                )
                if approval_result:
                    self.logger.info(f"Token approval completed: {approval_result}")

                # Step 3: Execute transaction
                tx_hash = await self._execute_transfer_transaction(
                    cdp_wallet_provider, quote_data
                )

                # Step 4: Monitor status and return result
                return await self._finalize_transfer(
                    client, tx_hash, from_chain, to_chain, quote_data
                )

        except Exception as e:
            self.logger.error("LiFi_Error: %s", str(e))
            return f"An unexpected error occurred: {str(e)}"

    async def _get_cdp_wallet_provider(self, agent_id: str):
        """Get CDP wallet provider with error handling."""
        try:
            cdp_client = await get_cdp_client(agent_id, self.skill_store)
            if not cdp_client:
                return "CDP client not available. Please ensure your agent has CDP wallet configuration."

            cdp_wallet_provider = await cdp_client.get_wallet_provider()
            if not cdp_wallet_provider:
                return "CDP wallet provider not configured. Please set up your agent's CDP wallet first."

            return cdp_wallet_provider

        except Exception as e:
            self.logger.error("LiFi_CDP_Error: %s", str(e))
            return f"Cannot access CDP wallet: {str(e)}\n\nPlease ensure your agent has a properly configured CDP wallet with sufficient funds."

    async def _get_quote(
        self,
        client: httpx.AsyncClient,
        from_chain: str,
        to_chain: str,
        from_token: str,
        to_token: str,
        from_amount: str,
        slippage: float,
        from_address: str,
    ) -> Dict[str, Any]:
        """Get quote from LiFi API."""
        api_params = build_quote_params(
            from_chain,
            to_chain,
            from_token,
            to_token,
            from_amount,
            slippage,
            from_address,
        )

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

        # Validate transaction request
        transaction_request = data.get("transactionRequest")
        if not transaction_request:
            return "No transaction request found in the quote. Cannot execute transfer."

        return data

    async def _handle_token_approval(
        self, wallet_provider, quote_data: Dict[str, Any]
    ) -> Optional[str]:
        """Handle ERC20 token approval if needed."""
        estimate = quote_data.get("estimate", {})
        approval_address = estimate.get("approvalAddress")
        from_token_info = quote_data.get("action", {}).get("fromToken", {})
        from_token_address = from_token_info.get("address", "")
        from_amount = quote_data.get("action", {}).get("fromAmount", "0")

        # Skip approval for native tokens
        if is_native_token(from_token_address) or not approval_address:
            return None

        self.logger.info("Checking token approval for ERC20 transfer...")

        try:
            return await self._check_and_set_allowance(
                wallet_provider, from_token_address, approval_address, from_amount
            )
        except Exception as e:
            self.logger.error("LiFi_Token_Approval_Error: %s", str(e))
            raise Exception(f"Failed to approve token: {str(e)}")

    async def _execute_transfer_transaction(
        self, wallet_provider, quote_data: Dict[str, Any]
    ) -> str:
        """Execute the main transfer transaction."""
        transaction_request = quote_data.get("transactionRequest")

        try:
            tx_params = prepare_transaction_params(transaction_request)
            self.logger.info(
                f"Sending transaction to {tx_params['to']} with value {tx_params['value']}"
            )

            # Send transaction
            tx_hash = wallet_provider.send_transaction(tx_params)

            # Wait for confirmation
            receipt = wallet_provider.wait_for_transaction_receipt(tx_hash)
            if not receipt or receipt.get("status") == 0:
                raise Exception(f"Transaction failed: {tx_hash}")

            return tx_hash

        except Exception as e:
            self.logger.error("LiFi_Execution_Error: %s", str(e))
            raise Exception(f"Failed to execute transaction: {str(e)}")

    async def _finalize_transfer(
        self,
        client: httpx.AsyncClient,
        tx_hash: str,
        from_chain: str,
        to_chain: str,
        quote_data: Dict[str, Any],
    ) -> str:
        """Finalize transfer and return formatted result."""
        self.logger.info(f"Transaction sent: {tx_hash}")

        # Get chain ID for explorer URL
        from_chain_id = convert_chain_to_id(from_chain)

        # Extract token info for result formatting
        action = quote_data.get("action", {})
        from_token_info = action.get("fromToken", {})
        to_token_info = action.get("toToken", {})

        token_info = {
            "symbol": f"{from_token_info.get('symbol', 'Unknown')} → {to_token_info.get('symbol', 'Unknown')}",
            "amount": format_amount(
                action.get("fromAmount", "0"), from_token_info.get("decimals", 18)
            ),
        }

        # Format transaction result with explorer URL
        transaction_result = format_transaction_result(
            tx_hash, from_chain_id, token_info
        )

        # Format quote details
        formatted_quote = self._format_quote_result(quote_data)

        # Handle cross-chain vs same-chain transfers
        if from_chain.lower() != to_chain.lower():
            self.logger.info("Monitoring cross-chain transfer status...")
            status_result = await self._monitor_transfer_status(
                client, tx_hash, from_chain, to_chain
            )

            return f"""**Token Transfer Executed Successfully**

{transaction_result}
{status_result}

{formatted_quote}
"""
        else:
            return f"""**Token Swap Executed Successfully**

{transaction_result}
**Status:** Completed (same-chain swap)

{formatted_quote}
"""

    async def _monitor_transfer_status(
        self, client: httpx.AsyncClient, tx_hash: str, from_chain: str, to_chain: str
    ) -> str:
        """Monitor the status of a cross-chain transfer."""
        max_attempts = min(self.max_execution_time // 10, 30)  # Check every 10 seconds
        attempt = 0

        while attempt < max_attempts:
            try:
                status_response = await client.get(
                    f"{self.api_url}/status",
                    params={
                        "txHash": tx_hash,
                        "fromChain": from_chain,
                        "toChain": to_chain,
                    },
                    timeout=10.0,
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get("status", "UNKNOWN")

                    if status == "DONE":
                        receiving_tx = status_data.get("receiving", {}).get("txHash")
                        if receiving_tx:
                            return (
                                f"**Status:** Complete (destination tx: {receiving_tx})"
                            )
                        else:
                            return "**Status:** Complete"
                    elif status == "FAILED":
                        return "**Status:** Failed"
                    elif status in ["PENDING", "NOT_FOUND"]:
                        # Continue monitoring
                        pass
                    else:
                        return f"**Status:** {status}"

            except Exception as e:
                self.logger.warning(
                    f"Status check failed (attempt {attempt + 1}): {str(e)}"
                )

            attempt += 1
            if attempt < max_attempts:
                await asyncio.sleep(10)  # Wait 10 seconds before next check

        return "**Status:** Processing (monitoring timed out, but transfer may still complete)"

    async def _check_and_set_allowance(
        self,
        wallet_provider,
        token_address: str,
        approval_address: str,
        amount: str,
    ) -> Optional[str]:
        """Check if token allowance is sufficient and set approval if needed."""
        try:
            # Normalize addresses
            token_address = Web3.to_checksum_address(token_address)
            approval_address = Web3.to_checksum_address(approval_address)
            wallet_address = wallet_provider.get_address()

            # Check current allowance
            try:
                current_allowance = wallet_provider.read_contract(
                    contract_address=token_address,
                    abi=ERC20_ABI,
                    function_name="allowance",
                    args=[wallet_address, approval_address],
                )

                required_amount = int(amount)

                if current_allowance >= required_amount:
                    self.logger.info(
                        f"Sufficient allowance already exists: {current_allowance}"
                    )
                    return None  # No approval needed

            except Exception as e:
                self.logger.warning(f"Could not check current allowance: {str(e)}")
                # Continue with approval anyway

            # Set approval for the required amount
            self.logger.info(
                f"Setting token approval for {amount} tokens to {approval_address}"
            )

            # Create approval transaction
            approve_data = create_erc20_approve_data(approval_address, amount)

            # Send approval transaction
            approval_tx_hash = wallet_provider.send_transaction(
                {
                    "to": token_address,
                    "data": approve_data,
                    "value": 0,
                }
            )

            # Wait for approval transaction confirmation
            receipt = wallet_provider.wait_for_transaction_receipt(approval_tx_hash)

            if not receipt or receipt.get("status") == 0:
                raise Exception(f"Approval transaction failed: {approval_tx_hash}")

            return approval_tx_hash

        except Exception as e:
            self.logger.error(f"Token approval failed: {str(e)}")
            raise Exception(f"Failed to approve token transfer: {str(e)}")
