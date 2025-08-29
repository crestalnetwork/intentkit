from typing import List, Optional, Tuple, Type

from pydantic import BaseModel, Field
from web3.exceptions import ContractLogicError

from intentkit.models.chat import ChatMessageAttachment, ChatMessageAttachmentType
from intentkit.skills.xmtp.base import XmtpBaseTool


class TransferInput(BaseModel):
    """Input for XMTP transfer skill."""

    from_address: str = Field(description="The sender address for the transfer")
    to_address: str = Field(description="The recipient address for the transfer")
    amount: str = Field(
        description="The amount to transfer in human-readable format (e.g., '1.5' for 1.5 ETH, '100' for 100 USDC). Do NOT multiply by token decimals."
    )
    currency: str = Field(description="Currency symbol (e.g., 'ETH', 'USDC', 'NATION')")
    token_contract_address: Optional[str] = Field(
        default=None,
        description="Token contract address for ERC20 transfers. Leave empty for ETH transfers.",
    )


class XmtpTransfer(XmtpBaseTool):
    """Skill for creating XMTP transfer transactions."""

    name: str = "xmtp_transfer"
    description: str = """Create an XMTP transaction request for transferring ETH or ERC20 tokens.
    This skill generates a wallet_sendCalls transaction request according to XMTP protocol 
    that can be sent to users for signing. 
    Supports Ethereum, Polygon, Base, Arbitrum, and Optimism networks (both mainnet and testnet).
    """
    args_schema: Type[BaseModel] = TransferInput

    async def _arun(
        self,
        from_address: str,
        to_address: str,
        amount: str,
        currency: str,
        token_contract_address: Optional[str],
    ) -> Tuple[str, List[ChatMessageAttachment]]:
        """Create an XMTP transfer transaction request.

        Args:
            from_address: The sender address
            to_address: The recipient address
            amount: Amount to transfer
            currency: Currency symbol
            token_contract_address: Token contract address (None for ETH)

        Returns:
            Tuple of (content_message, list_of_attachments)
        """
        # Get context and check network
        context = self.get_context()
        agent = context.agent

        # Validate network and get chain ID
        chain_id_hex = self.validate_network_and_get_chain_id(
            agent.network_id, "transfer"
        )

        # Validate token contract and get decimals
        if token_contract_address:
            # Validate ERC20 contract and get token info
            web3 = self.web3_client()

            # ERC20 ABI for symbol() and decimals() functions
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [],
                    "name": "symbol",
                    "outputs": [{"name": "", "type": "string"}],
                    "type": "function",
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function",
                },
            ]

            try:
                # Create contract instance
                contract = web3.eth.contract(
                    address=web3.to_checksum_address(token_contract_address),
                    abi=erc20_abi,
                )

                # Get token symbol and decimals
                token_symbol = contract.functions.symbol().call()
                decimals = contract.functions.decimals().call()

                # Validate symbol matches currency (case insensitive)
                if token_symbol.upper() != currency.upper():
                    raise ValueError(
                        f"Token symbol mismatch: contract symbol is '{token_symbol}', "
                        f"but currency parameter is '{currency}'"
                    )

            except ContractLogicError:
                raise ValueError(
                    f"Invalid ERC20 contract address: {token_contract_address}. "
                    "The address does not point to a valid ERC20 token contract."
                )
            except Exception as e:
                raise ValueError(
                    f"Failed to validate ERC20 contract {token_contract_address}: {str(e)}"
                )
        else:
            # For ETH transfers, use 18 decimals
            decimals = 18
            # Validate currency is ETH for native transfers
            if currency.upper() != "ETH":
                raise ValueError(
                    f"For native transfers, currency must be 'ETH', got '{currency}'"
                )

        # Calculate amount in smallest unit (wei for ETH, token units for ERC20)
        amount_int = int(float(amount) * (10**decimals))

        if token_contract_address:
            # ERC20 Token Transfer
            transaction_to = token_contract_address
            transaction_value = "0x0"  # No ETH value for token transfers

            # Create ERC20 transfer function call data
            # Function signature: transfer(address,uint256)
            # Method ID: First 4 bytes of keccak256("transfer(address,uint256)")
            method_id = "0xa9059cbb"  # transfer(address,uint256) method ID

            # Encode to_address (32 bytes, left-padded)
            to_address_clean = to_address.replace("0x", "")
            to_address_padded = to_address_clean.zfill(64)

            # Encode amount (32 bytes, left-padded)
            amount_hex = hex(amount_int)[2:]  # Remove 0x prefix
            amount_padded = amount_hex.zfill(64)

            # Combine method ID + padded address + padded amount
            call_data = method_id + to_address_padded + amount_padded

            description = f"Send {amount} {currency} to {to_address}"
            metadata = {
                "description": description,
                "transactionType": "erc20_transfer",
                "currency": currency,
                "amount": amount_int,
                "decimals": decimals,
                "toAddress": to_address,
                "tokenContract": token_contract_address,
            }
        else:
            # ETH Transfer
            transaction_to = to_address
            transaction_value = hex(amount_int)
            call_data = "0x"  # No call data for simple ETH transfer

            description = f"Send {amount} {currency} to {to_address}"
            metadata = {
                "description": description,
                "transactionType": "transfer",
                "currency": currency,
                "amount": amount_int,
                "decimals": decimals,
                "toAddress": to_address,
            }

        # Create XMTP wallet_sendCalls transaction request
        wallet_send_calls = {
            "version": "1.0",
            "from": from_address,
            "chainId": chain_id_hex,
            "calls": [
                {
                    "to": transaction_to,
                    "value": transaction_value,
                    "data": call_data,
                    "metadata": metadata,
                }
            ],
        }

        # Create ChatMessageAttachment
        attachment: ChatMessageAttachment = {
            "type": ChatMessageAttachmentType.XMTP,
            "url": None,
            "json": wallet_send_calls,
        }

        # Create user message
        content_message = (
            f"💸 Transfer transaction ready!\n\n"
            f"**Details:**\n"
            f"• Amount: {amount} {currency}\n"
            f"• To: {to_address}\n"
            f"• Network: {agent.network_id}\n"
            f"• Type: {'ERC20 Token' if token_contract_address else 'Native ETH'}\n\n"
            f"Please review the transaction details and sign to execute the transfer."
        )

        return content_message, [attachment]
