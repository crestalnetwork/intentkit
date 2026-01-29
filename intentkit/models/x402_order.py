"""X402 Order model for recording agent-initiated x402 transactions."""

import logging
from datetime import datetime
from typing import Annotated

from epyxid import XID
from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import BigInteger, DateTime, Integer, String, desc, func, select
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.config.db import get_session

logger = logging.getLogger(__name__)


class X402OrderBase(BaseModel):
    """Base fields for x402 order."""

    agent_id: Annotated[
        str, PydanticField(description="Agent that initiated the transaction")
    ]
    chat_id: Annotated[str, PydanticField(description="Chat/conversation ID")]
    user_id: Annotated[
        str | None, PydanticField(description="User ID from context")
    ] = None
    task_id: Annotated[str | None, PydanticField(description="Autonomous task ID")] = (
        None
    )
    skill_name: Annotated[
        str, PydanticField(description="Skill name (x402_pay, x402_http_request)")
    ]
    method: Annotated[str, PydanticField(description="HTTP method (GET/POST)")]
    url: Annotated[str, PydanticField(description="Target URL")]
    max_value: Annotated[
        int | None, PydanticField(description="Max payment limit (x402_pay only)")
    ] = None
    amount: Annotated[int, PydanticField(description="Payment amount in base units")]
    asset: Annotated[str, PydanticField(description="Payment asset (e.g., USDC)")]
    network: Annotated[str, PydanticField(description="Payment network")]
    pay_to: Annotated[str, PydanticField(description="Recipient address")]
    payer: Annotated[str | None, PydanticField(description="Payer address")] = None
    tx_hash: Annotated[str | None, PydanticField(description="Transaction hash")] = None
    status: Annotated[
        str, PydanticField(description="Status: pending, success, failed")
    ]
    error: Annotated[
        str | None, PydanticField(description="Error message if failed")
    ] = None
    http_status: Annotated[
        int | None, PydanticField(description="HTTP response status code")
    ] = None
    description: Annotated[
        str | None, PydanticField(description="Payment description from x402 protocol")
    ] = None


class X402OrderCreate(X402OrderBase):
    """Model for creating a new x402 order."""

    pass


class X402Order(X402OrderBase):
    """Full x402 order model with auto-generated fields."""

    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, PydanticField(description="Unique identifier for the order")]
    created_at: Annotated[datetime, PydanticField(description="Timestamp when created")]

    @classmethod
    async def create(cls, order: X402OrderCreate) -> "X402Order":
        """Create and save a new x402 order record.

        Args:
            order: The order creation data

        Returns:
            The created X402Order instance
        """
        async with get_session() as session:
            db_order = X402OrderTable(
                agent_id=order.agent_id,
                chat_id=order.chat_id,
                user_id=order.user_id,
                task_id=order.task_id,
                skill_name=order.skill_name,
                method=order.method,
                url=order.url,
                max_value=order.max_value,
                amount=order.amount,
                asset=order.asset,
                network=order.network,
                pay_to=order.pay_to,
                payer=order.payer,
                tx_hash=order.tx_hash,
                status=order.status,
                error=order.error,
                http_status=order.http_status,
                description=order.description,
            )
            session.add(db_order)
            await session.commit()
            await session.refresh(db_order)
            return cls.model_validate(db_order)

    @classmethod
    async def get_by_agent(cls, agent_id: str, limit: int = 5) -> list["X402Order"]:
        """Get recent successful orders for a specific agent.

        Args:
            agent_id: The agent ID to filter by
            limit: Maximum number of orders to return (default 5)

        Returns:
            List of X402Order instances with status='success', ordered by created_at descending
        """
        async with get_session() as session:
            result = await session.execute(
                select(X402OrderTable)
                .where(X402OrderTable.agent_id == agent_id)
                .where(X402OrderTable.status == "success")
                .order_by(desc(X402OrderTable.created_at))
                .limit(limit)
            )
            rows = result.scalars().all()
            return [cls.model_validate(row) for row in rows]


class X402OrderTable(Base):
    """SQLAlchemy table model for x402 orders."""

    __tablename__ = "x402_orders"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(XID()),
        comment="Unique identifier for the order",
    )
    agent_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
        comment="Agent that initiated the transaction",
    )
    chat_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True, comment="Chat/conversation ID"
    )
    user_id: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="User ID from context"
    )
    task_id: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Autonomous task ID"
    )
    skill_name: Mapped[str] = mapped_column(
        String, nullable=False, comment="Skill name"
    )
    method: Mapped[str] = mapped_column(String, nullable=False, comment="HTTP method")
    url: Mapped[str] = mapped_column(String, nullable=False, comment="Target URL")
    max_value: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Max payment limit"
    )
    amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Payment amount in base units"
    )
    asset: Mapped[str] = mapped_column(String, nullable=False, comment="Payment asset")
    network: Mapped[str] = mapped_column(
        String, nullable=False, comment="Payment network"
    )
    pay_to: Mapped[str] = mapped_column(
        String, nullable=False, comment="Recipient address"
    )
    payer: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Payer address"
    )
    tx_hash: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Transaction hash"
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, index=True, comment="Status: pending, success, failed"
    )
    error: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Error message"
    )
    http_status: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="HTTP response status code"
    )
    description: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Payment description from x402 protocol"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Timestamp when created",
    )
