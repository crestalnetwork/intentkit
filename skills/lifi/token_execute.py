from typing import Any, Dict, List, Optional, Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from clients.cdp import get_cdp_client
from skills.lifi.base import LiFiBaseTool
from skills.lifi.token_quote import TokenQuote


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
        description="The maximum allowed slippage for the transaction (0.03 represents 3%).",
    )


class TokenExecute(LiFiBaseTool):
    """Tool for executing token transfers across chains using LiFi.

    This tool executes actual token transfers and swaps using the CDP wallet.
    Requires a properly configured CDP wallet to work.
    """

    name: str = "token_execute"
    description: str = (
        "Execute a token transfer across blockchains or swap tokens on the same chain.\n"
        "This requires a CDP wallet with sufficient funds.\n"
        "Use token_quote first to check rates before executing."
    )
    args_schema: Type[BaseModel] = TokenExecuteInput
    api_url: str = "https://li.quest/v1"

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
        # Use TokenQuote for quote formatting
        self.quote_tool = TokenQuote(
            skill_store=skill_store,
            default_slippage=default_slippage,
            allowed_chains=allowed_chains,
        )

    def _format_quote_result(self, data: Dict[str, Any]) -> str:
        """Format quote result using the quote tool's formatting function."""
        if self.quote_tool:
            return self.quote_tool._format_quote_result(data)

        # Fallback if quote_tool is not available
        action = data.get("action", {})
        estimate = data.get("estimate", {})
        from_token = action.get("fromToken", {}).get("symbol", "Unknown")
        to_token = action.get("toToken", {}).get("symbol", "Unknown")
        to_amount = estimate.get("toAmount", "0")

        return (
            f"Transfer from {from_token} to {to_token}, estimated amount: {to_amount}"
        )

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
        """Execute a token transfer."""
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

            # Get agent context for CDP wallet
            context = self.context_from_config(config)
            agent_id = context.agent.id

            async with httpx.AsyncClient() as client:
                # Get CDP client and wallet
                cdp_client = await get_cdp_client(agent_id, self.skill_store)

                try:
                    wallet = await cdp_client.get_wallet()
                except AttributeError:
                    self.logger.error("LiFi_CDP_Error: wallet not configured")
                    return "Cannot execute token transfer: CDP wallet is not properly configured. Please ensure your agent has a CDP wallet set up."
                except Exception as e:
                    self.logger.error("LiFi_Error: %s", str(e))
                    return f"Error accessing wallet: {str(e)}"

                # Verify wallet is available
                if "wallet" not in locals():
                    return "Cannot execute token transfer: No wallet available"

                from_address = (
                    wallet.addresses[0].address_id if wallet.addresses else ""
                )

                if not from_address:
                    return "No wallet address available for transfer. Please check your CDP wallet configuration."

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

                # For execution mode, perform the actual token transfer
                transaction_request = data.get("transactionRequest")
                if not transaction_request:
                    return "No transaction request found in the quote. Cannot execute transfer."

                # Check and set approval for ERC20 tokens if needed
                estimate = data.get("estimate", {})
                approval_address = estimate.get("approvalAddress")
                from_token_info = data.get("action", {}).get("fromToken", {})
                from_token_address = from_token_info.get("address")

                # If not native token and approval needed
                if (
                    from_token_address != "0x0000000000000000000000000000000000000000"
                    and from_token_address != ""
                    and approval_address
                ):
                    try:
                        approval_result = await self._check_and_set_allowance(
                            wallet,
                            from_token_address,
                            approval_address,
                            from_amount,
                            from_chain,
                        )
                    except Exception as e:
                        self.logger.error("LiFi_Token_Approval_Error: %s", str(e))
                        return f"Failed to approve token: {str(e)}"

                # Execute transaction
                try:
                    tx_hash = await self._execute_transaction(
                        wallet, transaction_request, from_chain
                    )

                    # Check transaction status
                    try:
                        status_response = await client.get(
                            f"{self.api_url}/status",
                            params={
                                "txHash": tx_hash,
                                "fromChain": from_chain,
                                "toChain": to_chain,
                            },
                            timeout=min(30.0, self.max_execution_time),
                        )
                    except Exception as e:
                        self.logger.error("LiFi_Status_Error: %s", str(e))
                        return f"Transaction sent: {tx_hash}\nFailed to get status: {str(e)}"

                    if status_response.status_code != 200:
                        return f"Transaction sent: {tx_hash}\nFailed to get status: {status_response.status_code} - {status_response.text}"

                    status_data = status_response.json()

                    # Return transaction summary
                    formatted_quote = self._format_quote_result(data)
                    return f"""
### Transfer Executed

**Transaction Hash:** {tx_hash}
**Status:** {status_data.get("status", "PENDING")}
**Explorer Link:** {status_data.get("lifiExplorerLink", "")}

{formatted_quote}
"""

                except Exception as e:
                    self.logger.error("LiFi_Execution_Error: %s", str(e))
                    return f"Failed to execute transaction: {str(e)}"

        except Exception as e:
            self.logger.error("LiFi_Error: %s", str(e))
            return f"An error occurred: {str(e)}"

    async def _check_and_set_allowance(
        self,
        wallet,
        token_address: str,
        approval_address: str,
        amount: str,
        chain_id: str,
    ) -> Optional[str]:
        """Check and set token allowance for transfer if needed."""
        try:
            # Get the wallet address
            owner_address = wallet.addresses[0].address_id

            # Check current allowance
            allowance_data = self._encode_allowance_data(
                owner_address, approval_address
            )

            try:
                allowance_result = await wallet.call_contract(
                    to_address=token_address, data=allowance_data, chain_id=chain_id
                )
            except Exception as e:
                self.logger.error("LiFi_Allowance_Error: %s", str(e))
                raise Exception(f"Failed to check token allowance: {str(e)}")

            # Parse the result
            current_allowance = (
                int(allowance_result, 16)
                if allowance_result.startswith("0x")
                else int(allowance_result)
            )
            amount_int = int(amount)

            # If allowance is less than amount, approve more
            if current_allowance < amount_int:
                # Use max approval amount to save gas on future transfers
                max_approval_amount = 2**256 - 1

                # Encode approval data
                approve_data = self._encode_approve_data(
                    approval_address, str(max_approval_amount)
                )

                # Send approval transaction
                try:
                    approval_tx = await wallet.send_transaction(
                        to=token_address, data=approve_data, chain_id=chain_id
                    )
                except Exception as e:
                    self.logger.error("LiFi_Approval_Tx_Error: %s", str(e))
                    raise Exception(f"Failed to send approval transaction: {str(e)}")

                return approval_tx.hash

            # Already approved
            return None

        except Exception as e:
            self.logger.error("LiFi_Allowance_Error: %s", str(e))
            raise Exception(f"Failed to check/set token allowance: {str(e)}")

    def _encode_allowance_data(self, owner_address: str, spender_address: str) -> str:
        """Encode allowance function call data for ERC20 contract."""
        # Function selector for allowance(address,address)
        function_selector = "0xdd62ed3e"

        # Pad addresses to 32 bytes
        owner_param = (
            owner_address[2:].lower().zfill(64)
            if owner_address.startswith("0x")
            else owner_address.lower().zfill(64)
        )
        spender_param = (
            spender_address[2:].lower().zfill(64)
            if spender_address.startswith("0x")
            else spender_address.lower().zfill(64)
        )

        # Combine function selector and parameters
        return function_selector + owner_param + spender_param

    def _encode_approve_data(self, spender_address: str, amount: str) -> str:
        """Encode approve function call data for ERC20 contract."""
        # Function selector for approve(address,uint256)
        function_selector = "0x095ea7b3"

        # Pad parameters to 32 bytes
        spender_param = (
            spender_address[2:].lower().zfill(64)
            if spender_address.startswith("0x")
            else spender_address.lower().zfill(64)
        )
        amount_int = int(amount)
        amount_param = hex(amount_int)[2:].zfill(64)

        # Combine function selector and parameters
        return function_selector + spender_param + amount_param

    async def _execute_transaction(
        self, wallet, transaction_request: Dict[str, Any], chain_id: str
    ) -> str:
        """Execute a transaction using the CDP wallet."""
        try:
            # Extract transaction data
            to_address = transaction_request.get("to")
            value = transaction_request.get("value", "0x0")
            data = transaction_request.get("data")

            # Validate required fields
            if not to_address:
                raise ValueError("Transaction request missing 'to' address")

            if not data:
                raise ValueError("Transaction request missing 'data'")

            # Convert value to int if hex
            if isinstance(value, str) and value.startswith("0x"):
                value_int = int(value, 16)
            else:
                value_int = int(value) if value else 0

            # Send transaction
            try:
                tx = await wallet.send_transaction(
                    to=to_address,
                    value=str(value_int) if value_int > 0 else None,
                    data=data,
                    chain_id=chain_id,
                )
            except Exception as e:
                self.logger.error("LiFi_Tx_Error: %s", str(e))
                raise Exception(
                    f"Error sending transaction through CDP wallet: {str(e)}"
                )

            return tx.hash

        except Exception as e:
            self.logger.error("LiFi_Tx_Error: %s", str(e))
            raise Exception(f"Failed to execute transaction: {str(e)}")
