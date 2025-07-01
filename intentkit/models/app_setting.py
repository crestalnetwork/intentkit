import json
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, List

from intentkit.models.base import Base
from intentkit.models.db import get_session
from intentkit.models.redis import get_redis
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Column, DateTime, String, func, select
from sqlalchemy.dialects.postgresql import JSON, JSONB


class AppSettingTable(Base):
    """App settings database table model."""

    __tablename__ = "app_settings"

    key = Column(
        String,
        primary_key=True,
    )
    value = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PaymentSettings(BaseModel):
    """Payment settings model."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "credit_per_usdc": 1000,
                "fee_platform_percentage": 100,
                "fee_dev_percentage": 20,
                "agent_whitelist_enabled": False,
                "agent_whitelist": [],
            }
        }
    )

    credit_per_usdc: Annotated[
        Decimal,
        Field(default=Decimal("1000"), description="Number of credits per USDC"),
    ]
    fee_platform_percentage: Annotated[
        Decimal,
        Field(
            default=Decimal("100"), description="Platform fee percentage", ge=0, le=100
        ),
    ]
    fee_dev_percentage: Annotated[
        Decimal,
        Field(
            default=Decimal("20"), description="Developer fee percentage", ge=0, le=100
        ),
    ]
    agent_whitelist_enabled: Annotated[
        bool,
        Field(default=False, description="Whether agent whitelist is enabled"),
    ]
    agent_whitelist: Annotated[
        List[str],
        Field(default_factory=list, description="List of whitelisted agent IDs"),
    ]

    @field_validator("credit_per_usdc", "fee_platform_percentage", "fee_dev_percentage")
    @classmethod
    def round_decimal(cls, v: Any) -> Decimal:
        """Round decimal values to 4 decimal places."""
        if isinstance(v, Decimal):
            return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif isinstance(v, (int, float)):
            return Decimal(str(v)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return v


class AppSetting(BaseModel):
    """App setting model with all fields."""

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(timespec="milliseconds"),
        },
    )

    key: Annotated[str, Field(description="Setting key")]
    value: Annotated[Any, Field(description="Setting value as JSON")]
    created_at: Annotated[
        datetime, Field(description="Timestamp when this setting was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this setting was last updated")
    ]

    @staticmethod
    async def payment() -> PaymentSettings:
        """Get payment settings from the database with Redis caching.

        The settings are cached in Redis for 3 minutes.

        Returns:
            PaymentSettings: Payment settings
        """
        # Redis cache key for payment settings
        cache_key = "intentkit:app:settings:payment"
        cache_ttl = 180  # 3 minutes in seconds

        # Try to get from Redis cache first
        redis = get_redis()
        cached_data = await redis.get(cache_key)

        if cached_data:
            # If found in cache, deserialize and return
            try:
                payment_data = json.loads(cached_data)
                return PaymentSettings(**payment_data)
            except (json.JSONDecodeError, TypeError):
                # If cache is corrupted, invalidate it
                await redis.delete(cache_key)

        # If not in cache or cache is invalid, get from database
        async with get_session() as session:
            # Query the database for the payment settings
            stmt = select(AppSettingTable).where(AppSettingTable.key == "payment")
            setting = await session.scalar(stmt)

            # If settings don't exist, use default settings
            if not setting:
                payment_settings = PaymentSettings()
            else:
                # Convert the JSON value to PaymentSettings
                payment_settings = PaymentSettings(**setting.value)

            # Cache the settings in Redis
            await redis.set(
                cache_key,
                json.dumps(payment_settings.model_dump(mode="json")),
                ex=cache_ttl,
            )

            return payment_settings
