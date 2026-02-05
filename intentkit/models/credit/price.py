from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Annotated, Any

from epyxid import XID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    DateTime,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base


class PriceEntity(str, Enum):
    """Type of credit price."""

    SKILL_CALL = "skill_call"


class DiscountType(str, Enum):
    """Type of discount."""

    STANDARD = "standard"
    SELF_KEY = "self_key"


DEFAULT_SKILL_CALL_PRICE = Decimal("10.0000")
DEFAULT_SKILL_CALL_SELF_KEY_PRICE = Decimal("5.0000")


class CreditPriceTable(Base):
    """Credit price database table model.

    Stores price information for different types of services.
    """

    __tablename__ = "credit_prices"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )
    price_entity: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    price_entity_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    discount_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
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


class CreditPrice(BaseModel):
    """Credit price model with all fields."""

    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat(timespec="milliseconds")},
    )

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the credit price",
        ),
    ]
    price_entity: Annotated[
        PriceEntity, Field(description="Type of the price (agent or skill_call)")
    ]
    price_entity_id: Annotated[
        str, Field(description="ID of the price entity, the skill is the name")
    ]
    discount_type: Annotated[
        DiscountType,
        Field(default=DiscountType.STANDARD, description="Type of discount"),
    ]
    price: Annotated[Decimal, Field(default=Decimal("0"), description="Standard price")]

    @field_validator("price")
    @classmethod
    def round_decimal(cls, v: Any) -> Decimal:
        """Round decimal values to 4 decimal places."""
        if isinstance(v, Decimal):
            return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif isinstance(v, int | float):
            return Decimal(str(v)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return v

    created_at: Annotated[
        datetime, Field(description="Timestamp when this price was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this price was last updated")
    ]


class CreditPriceLogTable(Base):
    """Credit price log database table model.

    Records history of price changes.
    """

    __tablename__ = "credit_price_logs"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )
    price_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    old_price: Mapped[Decimal] = mapped_column(
        Numeric(22, 4),
        nullable=False,
    )
    new_price: Mapped[Decimal] = mapped_column(
        Numeric(22, 4),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    modified_by: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CreditPriceLog(BaseModel):
    """Credit price log model with all fields."""

    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat(timespec="milliseconds")},
    )

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the log entry",
        ),
    ]
    price_id: Annotated[str, Field(description="ID of the price that was modified")]
    old_price: Annotated[Decimal, Field(description="Previous standard price")]
    new_price: Annotated[Decimal, Field(description="New standard price")]

    @field_validator("old_price", "new_price")
    @classmethod
    def round_decimal(cls, v: Any) -> Decimal:
        """Round decimal values to 4 decimal places."""
        if isinstance(v, Decimal):
            return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif isinstance(v, int | float):
            return Decimal(str(v)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return v

    note: Annotated[str | None, Field(None, description="Note about the modification")]
    modified_by: Annotated[
        str, Field(description="ID of the user who made the modification")
    ]
    modified_at: Annotated[
        datetime, Field(description="Timestamp when the modification was made")
    ]
