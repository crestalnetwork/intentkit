from typing import List, Union
from pydantic import BaseModel, Field


class BalanceRequest(BaseModel):
    """
    Request for fetching balances from multiple blockchains.
    """
    chain: str = Field(..., description="Blockchain to check (e.g., ethereum, bsc, polygon)")
    wallet_address: str = Field(..., description="The wallet address to check balances for")


class BalanceResponse(BaseModel):
    """
    Response containing the balance information.
    """
    chain: str
    wallet_address: str
    balance: Union[str, float]


class MultiChainBalanceRequest(BaseModel):
    """
    Request to check balances on multiple chains.
    """
    requests: List[BalanceRequest]
