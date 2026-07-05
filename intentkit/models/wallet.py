"""Team wallets: crypto wallets owned at the team level.

A wallet belongs to a team, never to an agent. A team may own several
wallets; an agent chooses one per tool call by address (the pool is listed
in its system prompt), scoped to its own team.
Provider-specific payloads (Privy wallet ids, native private keys, ...) are
stored in ``wallet_data`` as JSON, mirroring the shapes previously kept in
``agent_data.privy_wallet_data`` / ``native_wallet_data``.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar, Literal

from epyxid import XID
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import DateTime, Float, Index, String, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.config.db import get_session
from intentkit.utils.error import IntentKitAPIError

WalletProviderLiteral = Literal["cdp", "native", "readonly", "safe", "privy"]

WALLET_PROVIDERS: tuple[str, ...] = ("cdp", "native", "readonly", "safe", "privy")


def wallet_owner_team(team_id: str | None) -> str:
    """The team a wallet must belong to for a given owner team id.

    Agents (and other resources) without a team fall back to the synthetic
    "system" team — the single home of this convention.
    """
    return team_id or "system"


# Wallet rows are effectively immutable after provisioning (address, provider
# and payload never change; only cosmetic fields like the spending limit do),
# and they sit on the hot path of every on-chain tool call. A short in-process
# TTL cache collapses the repeated primary-key lookups per agent turn.
_WALLET_CACHE_TTL = 60.0
_wallet_cache: dict[str, tuple[TeamWallet, float]] = {}


def _cache_put(wallet: TeamWallet) -> None:
    _wallet_cache[wallet.id] = (wallet, time.monotonic())


def _cache_drop(wallet_id: str) -> None:
    _wallet_cache.pop(wallet_id, None)


class TeamWalletTable(Base):
    """One crypto wallet owned by a team."""

    __tablename__: str = "team_wallets"
    __table_args__: Any = (
        Index("ix_team_wallets_team", "team_id"),
        # Names are the human handle in pickers; keep them unique per team.
        Index("ix_team_wallets_team_name", "team_id", "name", unique=True),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(XID())
    )
    team_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    wallet_provider: Mapped[str] = mapped_column(
        String, nullable=False, comment="cdp | native | readonly | safe | privy"
    )
    network_id: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Default network the wallet was provisioned for"
    )
    evm_wallet_address: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="EVM address (Safe address for safe wallets)"
    )
    solana_wallet_address: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Solana address"
    )
    wallet_data: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Provider-specific JSON payload"
    )
    weekly_spending_limit: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Weekly spending limit in USDC (safe wallets only)",
    )
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )


class TeamWallet(BaseModel):
    """Read model + persistence helpers for team wallets."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="Wallet ID")]
    team_id: Annotated[str, Field(description="Owning team ID")]
    name: Annotated[str, Field(description="Display name, unique within the team")]
    wallet_provider: Annotated[
        str, Field(description="cdp | native | readonly | safe | privy")
    ]
    network_id: Annotated[
        str | None,
        Field(default=None, description="Default network the wallet was created for"),
    ] = None
    evm_wallet_address: Annotated[
        str | None,
        Field(default=None, description="EVM address (Safe address for safe wallets)"),
    ] = None
    solana_wallet_address: Annotated[
        str | None, Field(default=None, description="Solana address")
    ] = None
    wallet_data: Annotated[
        str | None,
        # exclude + repr=False: the payload holds private keys / Privy ids and
        # must never reach API responses or logs.
        Field(
            default=None,
            description="Provider-specific JSON payload",
            exclude=True,
            repr=False,
        ),
    ] = None
    weekly_spending_limit: Annotated[
        float | None,
        Field(default=None, description="Weekly USDC spending limit (safe only)"),
    ] = None
    created_by: Annotated[str, Field(description="User who created the wallet")]
    created_at: Annotated[datetime, Field(description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(description="Last update timestamp")]

    @field_serializer("created_at", "updated_at")
    @classmethod
    def serialize_datetime(cls, v: datetime) -> str:
        return v.isoformat(timespec="milliseconds")

    def wallet_data_json(self) -> dict[str, Any]:
        """Parse the provider payload; empty dict when unset."""
        if not self.wallet_data:
            return {}
        return json.loads(self.wallet_data)

    @classmethod
    async def get(cls, wallet_id: str) -> TeamWallet | None:
        cached = _wallet_cache.get(wallet_id)
        if cached and time.monotonic() - cached[1] < _WALLET_CACHE_TTL:
            return cached[0]
        async with get_session() as db:
            item = await db.get(TeamWalletTable, wallet_id)
            wallet = cls.model_validate(item) if item else None
        if wallet:
            _cache_put(wallet)
        else:
            _cache_drop(wallet_id)
        return wallet

    @classmethod
    async def get_for_team(
        cls, wallet_id: str | None, team_id: str | None
    ) -> TeamWallet | None:
        """Resolve a wallet only when it belongs to the given owner team.

        The single team-ownership gate for read paths: pass the resource
        owner's team id (an agent's ``team_id``); None falls back to the
        synthetic "system" team.
        """
        if not wallet_id:
            return None
        wallet = await cls.get(wallet_id)
        if wallet is None or wallet.team_id != wallet_owner_team(team_id):
            return None
        return wallet

    @classmethod
    async def list_for_team(cls, team_id: str) -> list[TeamWallet]:
        """List a team's wallets, oldest first."""
        async with get_session() as db:
            stmt = (
                select(TeamWalletTable)
                .where(TeamWalletTable.team_id == team_id)
                .order_by(TeamWalletTable.created_at)
            )
            result = await db.scalars(stmt)
            return [cls.model_validate(row) for row in result]

    @classmethod
    async def get_by_address(cls, team_id: str, address: str) -> TeamWallet | None:
        """Resolve a team's wallet by its EVM address (case-insensitive)."""
        if not address:
            return None
        async with get_session() as db:
            stmt = select(TeamWalletTable).where(
                TeamWalletTable.team_id == team_id,
                func.lower(TeamWalletTable.evm_wallet_address) == address.lower(),
            )
            item = (await db.scalars(stmt)).first()
            wallet = cls.model_validate(item) if item else None
        if wallet:
            _cache_put(wallet)
        return wallet

    @classmethod
    async def create(
        cls,
        *,
        team_id: str,
        name: str,
        wallet_provider: str,
        created_by: str,
        wallet_id: str | None = None,
        network_id: str | None = None,
        evm_wallet_address: str | None = None,
        solana_wallet_address: str | None = None,
        wallet_data: str | None = None,
        weekly_spending_limit: float | None = None,
    ) -> TeamWallet:
        async with get_session() as db:
            record = TeamWalletTable(
                id=wallet_id or str(XID()),
                team_id=team_id,
                name=name,
                wallet_provider=wallet_provider,
                network_id=network_id,
                evm_wallet_address=evm_wallet_address,
                solana_wallet_address=solana_wallet_address,
                wallet_data=wallet_data,
                weekly_spending_limit=weekly_spending_limit,
                created_by=created_by,
            )
            db.add(record)
            try:
                await db.commit()
            except IntegrityError as e:
                # ix_team_wallets_team_name: names are unique per team
                raise IntentKitAPIError(
                    400,
                    "WalletNameTaken",
                    f"The team already has a wallet named '{name}'.",
                ) from e
            await db.refresh(record)
            wallet = cls.model_validate(record)
        _cache_put(wallet)
        return wallet

    _PATCHABLE_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "name",
            "network_id",
            "weekly_spending_limit",
            "wallet_data",
            "evm_wallet_address",
            "solana_wallet_address",
        }
    )

    @classmethod
    async def patch(cls, wallet_id: str, data: dict[str, Any]) -> TeamWallet | None:
        """Update selected mutable fields; returns the updated wallet or None if gone."""
        unknown = set(data) - cls._PATCHABLE_FIELDS
        if unknown:
            raise ValueError(f"Fields not patchable on TeamWallet: {sorted(unknown)}")
        async with get_session() as db:
            item = await db.get(TeamWalletTable, wallet_id)
            if not item:
                return None
            for key, value in data.items():
                setattr(item, key, value)
            db.add(item)
            await db.commit()
            await db.refresh(item)
            wallet = cls.model_validate(item)
        _cache_put(wallet)
        return wallet

    @classmethod
    async def delete(cls, wallet_id: str) -> None:
        async with get_session() as db:
            await db.execute(
                delete(TeamWalletTable).where(TeamWalletTable.id == wallet_id)
            )
            await db.commit()
        _cache_drop(wallet_id)
