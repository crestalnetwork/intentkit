"""fetching transaction history for a wallet."""

from typing import Dict, List, Optional, Type
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from skills.wallet.api import fetch_transaction_history
from skills.wallet.base import WalletBaseTool

logger = logging.getLogger(__name__)

class FetchTransactionHistoryInput(BaseModel):
    """Input for FetchTransactionHistory tool."""
    
    address: str = Field(..., description="Wallet address")
    chain_id: Optional[int] = Field(
        None, 
        description="Chain ID (if not specified, fetches from Ethereum mainnet)"
    )
    limit: Optional[int] = Field(
        100, 
        description="Maximum number of transactions to return"
    )
    cursor: Optional[str] = Field(
        None, 
        description="Cursor for pagination"
    )


class TokenTransfer(BaseModel):
    """Model for a token transfer within a transaction."""
    
    token_address: str = Field(..., description="Token contract address")
    token_name: Optional[str] = Field(None, description="Token name")
    token_symbol: Optional[str] = Field(None, description="Token symbol")
    token_decimals: Optional[int] = Field(None, description="Token decimals")
    from_address: str = Field(..., description="Sender address")
    to_address: str = Field(..., description="Recipient address")
    value: str = Field(..., description="Raw transfer value")
    value_decimal: Optional[float] = Field(None, description="Formatted decimal value")
    value_usd: Optional[float] = Field(None, description="USD value of transfer")


class Transaction(BaseModel):
    """Model for a transaction."""
    
    hash: str = Field(..., description="Transaction hash")
    block_number: int = Field(..., description="Block number")
    timestamp: datetime = Field(..., description="Transaction timestamp")
    from_address: str = Field(..., description="Sender address")
    to_address: Optional[str] = Field(None, description="Recipient address (None for contract creations)")
    value: str = Field(..., description="Raw native token value")
    value_decimal: float = Field(..., description="Formatted decimal value")
    value_usd: Optional[float] = Field(None, description="USD value of transaction")
    gas_price: str = Field(..., description="Gas price")
    gas_used: Optional[str] = Field(None, description="Gas used")
    fee: Optional[float] = Field(None, description="Transaction fee in native token")
    fee_usd: Optional[float] = Field(None, description="Transaction fee in USD")
    method: Optional[str] = Field(None, description="Contract method name if available")
    token_transfers: List[TokenTransfer] = Field(default_factory=list, description="Token transfers in this transaction")
    transaction_type: Optional[str] = Field(None, description="Transaction type (transfer, swap, approval, etc.)")
    chain: str = Field("eth", description="Blockchain network")


class TransactionHistoryOutput(BaseModel):
    """Output for FetchTransactionHistory tool."""
    
    address: str = Field(..., description="Wallet address")
    chain_id: Optional[int] = Field(None, description="Chain ID if specified")
    chain_name: Optional[str] = Field(None, description="Chain name if specified")
    transactions: List[Transaction] = Field(default_factory=list, description="List of transactions")
    total_count: Optional[int] = Field(None, description="Total count of transactions")
    page_size: int = Field(0, description="Page size")
    cursor: Optional[str] = Field(None, description="Cursor for pagination")
    error: Optional[str] = Field(None, description="Error message if any")


class FetchTransactionHistory(WalletBaseTool):
    """Tool for fetching transaction history for a wallet.
    
    This tool retrieves detailed transaction data for a wallet address,
    including token transfers, gas costs, and USD values when available.
    """

    name: str = "moralis_fetch_transaction_history"
    description: str = (
        "This tool fetches transaction history for a wallet address.\n"
        "Provide a wallet address and optionally a chain ID to get detailed transaction data.\n"
        "Returns:\n"
        "- Transaction details (hash, timestamp, value, etc.)\n"
        "- Transaction type (transfer, swap, approval, etc.)\n"
        "- Token movements (from, to, amount)\n"
        "- Gas costs\n"
        "Use this tool whenever a user wants to see their recent transactions."
    )
    args_schema: Type[BaseModel] = FetchTransactionHistoryInput

    async def _arun(
        self, 
        address: str, 
        chain_id: Optional[int] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
        **kwargs
    ) -> TransactionHistoryOutput:
        """Fetch transaction history for a wallet.
        
        Args:
            address: Wallet address to fetch transactions for
            chain_id: Chain ID to fetch transactions for (if None, fetches from Ethereum mainnet)
            limit: Maximum number of transactions to return
            cursor: Cursor for pagination
            
        Returns:
            TransactionHistoryOutput containing transaction history data
        """
        try:
            # Get context from config if available
            context = None
            if 'config' in kwargs:
                context = self.context_from_config(kwargs['config'])
            
            # Default to Ethereum mainnet if chain_id is not specified
            if chain_id is None:
                chain_id = 1  # Ethereum mainnet
            
            # Fetch transaction history
            tx_data = await fetch_transaction_history(
                self.api_key, 
                address, 
                chain_id, 
                cursor, 
                limit
            )
            
            if "error" in tx_data:
                return TransactionHistoryOutput(
                    address=address,
                    chain_id=chain_id,
                    chain_name=self._get_chain_name(chain_id),
                    error=tx_data["error"]
                )
            
            # Process the data
            chain_name = self._get_chain_name(chain_id)
            result = {
                "address": address,
                "chain_id": chain_id,
                "chain_name": chain_name,
                "transactions": [],
                "total_count": tx_data.get("total"),
                "page_size": tx_data.get("page_size", limit),
                "cursor": tx_data.get("cursor")
            }
            
            for tx in tx_data.get("result", []):
                # Process token transfers
                token_transfers = []
                if "token_transfers" in tx:
                    for transfer in tx["token_transfers"]:
                        token_transfer = TokenTransfer(
                            token_address=transfer.get("token_address", ""),
                            token_name=transfer.get("token_name"),
                            token_symbol=transfer.get("token_symbol"),
                            token_decimals=transfer.get("token_decimals"),
                            from_address=transfer.get("from_address", tx.get("from_address", "")),
                            to_address=transfer.get("to_address", ""),
                            value=transfer.get("value", "0"),
                            value_decimal=transfer.get("value_decimal"),
                            value_usd=transfer.get("value_usd")
                        )
                        token_transfers.append(token_transfer)
                
                # Determine transaction type based on method name or token transfers
                tx_type = None
                if "method" in tx:
                    method = tx["method"].lower() if tx["method"] else ""
                    if "transfer" in method:
                        tx_type = "transfer"
                    elif "swap" in method:
                        tx_type = "swap"
                    elif "approve" in method:
                        tx_type = "approval"
                    elif "withdraw" in method:
                        tx_type = "withdrawal"
                    elif "deposit" in method:
                        tx_type = "deposit"
                    elif "mint" in method:
                        tx_type = "mint"
                    elif "burn" in method:
                        tx_type = "burn"
                
                # If no method-based type, derive from token transfers
                if not tx_type and token_transfers:
                    tx_type = "token_transfer"
                
                # Create transaction
                try:
                    transaction = Transaction(
                        hash=tx.get("hash", ""),
                        block_number=int(tx.get("block_number", 0)),
                        timestamp=datetime.fromtimestamp(int(tx.get("block_timestamp", 0))),
                        from_address=tx.get("from_address", ""),
                        to_address=tx.get("to_address"),
                        value=tx.get("value", "0"),
                        value_decimal=float(tx.get("value_decimal", 0)),
                        value_usd=tx.get("value_usd"),
                        gas_price=tx.get("gas_price", "0"),
                        gas_used=tx.get("gas_used"),
                        fee=tx.get("fee"),
                        fee_usd=tx.get("fee_usd"),
                        method=tx.get("method"),
                        token_transfers=token_transfers,
                        transaction_type=tx_type,
                        chain=chain_name
                    )
                    
                    result["transactions"].append(transaction)
                except Exception as e:
                    logger.warning(f"Error processing transaction {tx.get('hash', '')}: {str(e)}")
                    continue
            
            return TransactionHistoryOutput(**result)
            
        except Exception as e:
            logger.error(f"Error fetching transaction history: {str(e)}")
            return TransactionHistoryOutput(
                address=address,
                chain_id=chain_id,
                chain_name=self._get_chain_name(chain_id) if chain_id else None,
                error=str(e)
            )