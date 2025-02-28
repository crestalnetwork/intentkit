from typing import Optional

from sqlmodel import Field, SQLModel, select

from models.db import get_session
from utils.chain import Network


class W3Token(SQLModel, table=True):
    """Model for storing token-specific data for web3 tools.

    This model uses a composite primary key of (symbol, chain_id) to store
    token data in a flexible way.

    Attributes:
        token_id: ID of the token
        symbol: Token symbol
    """

    __tablename__ = "w3_token"

    symbol: str = Field(primary_key=True)
    chain_id: str = Field(primary_key=True)
    is_well_known: bool = Field(nullable=False)
    name: str = Field(nullable=False)
    decimals: int = Field(nullable=False)
    address: str = Field(nullable=False)
    primary_address: str = Field(nullable=True)
    token_type: str = Field(nullable=True)
    protocol_slug: str = Field(nullable=True)

    @classmethod
    async def get(cls, symbol: str, network: Network) -> Optional["W3Token"]:
        async with get_session() as db:
            result = (
                await db.exec(
                    select(cls).where(
                        cls.symbol == symbol,
                        cls.chain_id == network.value.id,
                    )
                )
            ).first()
        return result

    @classmethod
    async def get_well_known(cls) -> list["W3Token"]:
        async with get_session() as db:
            result = (
                await db.exec(
                    select(cls).where(
                        cls.is_well_known,
                    )
                )
            ).all()
        return result

    async def save(self) -> None:
        async with get_session() as db:
            existing = (
                await db.exec(
                    select(self.__class__).where(
                        self.__class__.symbol == self.symbol,
                        self.__class__.chain_id == self.chain_id,
                    )
                )
            ).first()
            if existing:
                existing.is_well_known = self.is_well_known
                existing.name = self.name
                existing.decimals = self.decimals
                existing.address = self.address
                existing.primary_address = self.primary_address
                existing.token_type = self.token_type
                existing.protocol_slug = self.protocol_slug
                db.add(existing)
            else:
                db.add(self)
            await db.commit()
