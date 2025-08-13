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

        # Extract approval and swap calls if present (prefer QuoteSwapResult canonical fields)
        calls: list[dict] = []

        def to_xmtp_call(call_like, description: str) -> dict | None:
            if not call_like:
                return None
            # Attributes on QuoteSwapResult call-like objects
            to_value = getattr(call_like, "to", None) or getattr(
                call_like, "target", None
            )
            data_value = getattr(call_like, "data", None) or getattr(
                call_like, "calldata", None
            )
            value_value = getattr(call_like, "value", None)
            # Dict fallback
            if isinstance(call_like, dict):
                to_value = to_value or call_like.get("to") or call_like.get("target")
                data_value = (
                    data_value or call_like.get("data") or call_like.get("calldata")
                )
                value_value = value_value or call_like.get("value")
            if not to_value or not data_value:
                return None
            value_hex = (
                value_value
                if isinstance(value_value, str) and value_value.startswith("0x")
                else (hex(int(value_value)) if value_value is not None else "0x0")
            )
            data_hex = (
                data_value if str(data_value).startswith("0x") else f"0x{data_value}"
            )
            return {
                "to": to_value,
                "value": value_hex,
                "data": data_hex,
                "metadata": {
                    "description": description,
                    "transactionType": "swap_step",
                    "fromToken": from_token,
                    "toToken": to_token,
                    "amountIn": from_amount,
                    "slippageBps": slippage_bps,
                },
            }

        # Heuristics for various response shapes
        approval = (
            getattr(quote, "approval", None)
            or getattr(quote, "approval_call_data", None)
            or (quote.get("approval") if isinstance(quote, dict) else None)
            or (quote.get("approval_call_data") if isinstance(quote, dict) else None)
        )
        approval_xmtp = to_xmtp_call(approval, "Approve token spending if required")
        if approval_xmtp:
            calls.append(approval_xmtp)

        swap_call = (
            getattr(quote, "swap", None)
            or getattr(quote, "swap_call_data", None)
            or (quote.get("swap") if isinstance(quote, dict) else None)
            or (quote.get("swap_call_data") if isinstance(quote, dict) else None)
        )
        swap_xmtp = to_xmtp_call(swap_call, "Execute token swap")
        if swap_xmtp:
            calls.append(swap_xmtp)

        if not calls:
            # As a final fallback, some responses may provide a generic 'calls' list
            raw_calls = getattr(quote, "calls", None) or (
                quote.get("calls") if isinstance(quote, dict) else None
            )
            if isinstance(raw_calls, list):
                for idx, c in enumerate(raw_calls):
                    x = to_xmtp_call(c, f"Swap step {idx + 1}")
                    if x:
                        calls.append(x)

        if not calls:
            raise ValueError(
                "CDP swap quote did not return callable steps compatible with wallet_sendCalls"
            )

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

        # Human-friendly message
        content_message = (
            f"I created a swap transaction request to exchange {from_amount} units of {from_token} "
            f"for {to_token} on {agent.network_id}. Review and sign to execute."
        )

        return content_message, [attachment]
