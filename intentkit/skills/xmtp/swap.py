from typing import List, Tuple, Type

from pydantic import BaseModel, Field

from intentkit.clients.cdp import get_origin_cdp_client
from intentkit.models.chat import ChatMessageAttachment, ChatMessageAttachmentType
from intentkit.skills.xmtp.base import XmtpBaseTool


class SwapInput(BaseModel):
    """Input for XMTP swap skill.

    This creates an unsigned swap transaction attachment using CDP swap quote
    that a user can review and sign via XMTP wallet_sendCalls.
    """

    from_address: str = Field(description="The sender address for the swap")
    from_token: str = Field(
        description="The contract address of the token to swap from"
    )
    to_token: str = Field(description="The contract address of the token to swap to")
    from_amount: str = Field(
        description="The input amount in the smallest unit of from_token (as string)"
    )
    slippage_bps: int = Field(
        default=100,
        description="Maximum slippage in basis points (100 = 1%). Defaults to 100.",
    )


class XmtpSwap(XmtpBaseTool):
    """Skill for creating XMTP swap transactions using CDP swap quote.

    Generates a wallet_sendCalls transaction request to perform a token swap.
    May include an ERC20 approval call followed by the router swap call.
    Supports Base mainnet and Base Sepolia testnet.
    """

    name: str = "xmtp_swap"
    description: str = (
        "Create an XMTP transaction request for swapping tokens on Base using CDP swap quote. "
        "Returns a wallet_sendCalls payload that can include an optional approval call and the swap call. "
        "Only supports base-mainnet and base-sepolia."
    )
    args_schema: Type[BaseModel] = SwapInput

    async def _arun(
        self,
        from_address: str,
        from_token: str,
        to_token: str,
        from_amount: str,
        slippage_bps: int = 100,
    ) -> Tuple[str, List[ChatMessageAttachment]]:
        # Input validation
        if (
            not from_address
            or not from_address.startswith("0x")
            or len(from_address) != 42
        ):
            raise ValueError("from_address must be a valid Ethereum address")

        if not from_token or not from_token.startswith("0x") or len(from_token) != 42:
            raise ValueError("from_token must be a valid token contract address")

        if not to_token or not to_token.startswith("0x") or len(to_token) != 42:
            raise ValueError("to_token must be a valid token contract address")

        if from_token.lower() == to_token.lower():
            raise ValueError("from_token and to_token cannot be the same")

        try:
            amount_int = int(from_amount)
            if amount_int <= 0:
                raise ValueError("from_amount must be a positive integer")
        except ValueError as e:
            raise ValueError(f"from_amount must be a valid positive integer: {e}")

        if (
            not isinstance(slippage_bps, int)
            or slippage_bps < 0
            or slippage_bps > 10000
        ):
            raise ValueError("slippage_bps must be between 0 and 10000 (0% to 100%)")

        # Resolve agent context and target network
        context = self.get_context()
        agent = context.agent

        # ChainId mapping for XMTP wallet_sendCalls
        chain_id_hex_by_network = {
            "base-mainnet": "0x2105",  # 8453
            "base-sepolia": "0x14A34",  # 84532
        }

        if agent.network_id not in chain_id_hex_by_network:
            raise ValueError(
                f"XMTP swap only supports base-mainnet or base-sepolia. Current agent network: {agent.network_id}"
            )

        chain_id_hex = chain_id_hex_by_network[agent.network_id]

        # CDP network mapping for swap quote API
        # Reference: CDP SDK examples for swap quote and price
        # https://github.com/coinbase/cdp-sdk/blob/main/examples/python/evm/swaps/create_swap_quote.py
        network_for_cdp = {
            "base-mainnet": "base",
            "base-sepolia": "base-sepolia",
        }[agent.network_id]

        # Get CDP client from global origin helper (server-side credentials)
        cdp_client = get_origin_cdp_client(self.skill_store)

        # Call CDP to create swap quote and extract call datas
        # Be permissive with response shape across SDK versions
        try:
            # Attempt the canonical method per CDP SDK examples
            # create_swap_quote(from_token, to_token, from_amount, network, taker, slippage_bps, signer_address)
            # Note: Don't use async with context manager as get_origin_cdp_client returns a managed global client
            quote = await cdp_client.evm.create_swap_quote(
                from_token=from_token,
                to_token=to_token,
                from_amount=str(from_amount),
                network=network_for_cdp,
                taker=from_address,
                slippage_bps=slippage_bps,
                signer_address=from_address,
            )
        except Exception as e:  # pragma: no cover - defensive
            raise ValueError(f"Failed to create swap quote via CDP: {e!s}")

        # Extract transaction data from QuoteSwapResult
        # CDP returns a single transaction object with all necessary data
        calls: list[dict] = []

        # Validate that we have the required fields from CDP
        if not hasattr(quote, "to") or not hasattr(quote, "data"):
            raise ValueError(
                "CDP swap quote missing required transaction fields (to, data)"
            )

        # Format value field - ensure it's a hex string
        value_hex = "0x0"
        if hasattr(quote, "value") and quote.value:
            if isinstance(quote.value, str) and quote.value.startswith("0x"):
                value_hex = quote.value
            else:
                value_hex = hex(int(quote.value)) if quote.value != "0" else "0x0"

        # Format data field - ensure it has 0x prefix
        data_hex = quote.data if quote.data.startswith("0x") else f"0x{quote.data}"

        # Get expected output amount for metadata
        to_amount = getattr(quote, "to_amount", None) or "unknown"
        min_to_amount = getattr(quote, "min_to_amount", None) or "unknown"

        # Create the swap call following XMTP wallet_sendCalls format
        swap_call = {
            "to": quote.to,
            "value": value_hex,
            "data": data_hex,
            "metadata": {
                "description": f"Swap {from_amount} units of {from_token} for {to_token} (expected: {to_amount}, min: {min_to_amount})",
                "transactionType": "swap",
                "currency": from_token,
                "amount": int(from_amount),
                "toAddress": quote.to,
                "fromToken": from_token,
                "toToken": to_token,
                "expectedOutput": to_amount,
                "minimumOutput": min_to_amount,
                "slippageBps": slippage_bps,
                "network": agent.network_id,
            },
        }

        calls.append(swap_call)

        # Note: CDP's create_swap_quote already includes any necessary approvals
        # in the single transaction if needed, or handles them via Permit2 signatures

        # Build XMTP wallet_sendCalls payload
        wallet_send_calls = {
            "version": "1.0",
            "from": from_address,
            "chainId": chain_id_hex,
            "calls": calls,
        }

        # Attachment for chat
        attachment: ChatMessageAttachment = {
            "type": ChatMessageAttachmentType.XMTP,
            "url": None,
            "json": wallet_send_calls,
        }

        # Human-friendly message with more details
        expected_output = getattr(quote, "to_amount", "unknown")
        min_output = getattr(quote, "min_to_amount", "unknown")

        content_message = (
            f"🔄 Swap transaction ready!\n\n"
            f"**Details:**\n"
            f"• From: {from_amount} units of {from_token}\n"
            f"• To: {to_token}\n"
            f"• Expected output: {expected_output} units\n"
            f"• Minimum output: {min_output} units\n"
            f"• Network: {agent.network_id}\n"
            f"• Slippage: {slippage_bps / 100:.1f}%\n\n"
            f"Please review the transaction details and sign to execute the swap."
        )

        return content_message, [attachment]
