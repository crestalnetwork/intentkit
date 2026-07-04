"""Local API: Crypto Wallets — team wallets for the single-user deployment.

Same feature as the team API's ``app/team/wallet.py``, without auth: the
local deployment has one implicit user whose resources live under the
synthetic ``system`` team, so every endpoint operates on that team.
"""

import logging

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from intentkit.core.team.wallet import create_team_wallet
from intentkit.models.wallet import TeamWallet

from app.local.lead import LEAD_TEAM_ID, LEAD_USER_ID

logger = logging.getLogger(__name__)

wallet_router = APIRouter()


@wallet_router.get(
    "/wallets",
    response_model=list[TeamWallet],
    operation_id="list_wallets",
    summary="List wallets",
    tags=["Wallet"],
)
async def list_wallets() -> list[TeamWallet]:
    """List all crypto wallets of the local (system) team."""
    return await TeamWallet.list_for_team(LEAD_TEAM_ID)


class WalletCreateRequest(BaseModel):
    """Parameters for provisioning a new wallet."""

    name: str = Field(
        min_length=1, max_length=50, description="Display name, unique within the team"
    )
    wallet_provider: str = Field(
        description="cdp | native | readonly | safe | privy",
    )
    network_id: str | None = Field(
        default=None, description="Default network (defaults to base-mainnet)"
    )
    readonly_address: str | None = Field(
        default=None, description="Watched address (readonly wallets only)"
    )
    weekly_spending_limit: float | None = Field(
        default=None, ge=0.0, description="Weekly USDC spending limit (safe only)"
    )


@wallet_router.post(
    "/wallets",
    response_model=TeamWallet,
    status_code=201,
    operation_id="create_wallet",
    summary="Create a wallet",
    tags=["Wallet"],
)
async def create_wallet(body: WalletCreateRequest = Body(...)) -> TeamWallet:
    """Provision a new wallet owned by the local (system) team."""
    return await create_team_wallet(
        team_id=LEAD_TEAM_ID,
        name=body.name,
        wallet_provider=body.wallet_provider,
        created_by=LEAD_USER_ID,
        network_id=body.network_id,
        readonly_address=body.readonly_address,
        weekly_spending_limit=body.weekly_spending_limit,
    )
