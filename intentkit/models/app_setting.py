import time
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Annotated, Any, Dict, List

from intentkit.models.base import Base
from intentkit.models.db import get_session
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Column, DateTime, String, func, select
from sqlalchemy.dialects.postgresql import JSON, JSONB


class SystemMessageType(str, Enum):
    """Type of system message."""

    SERVICE_FEE_ERROR = "service_fee_error"
    DAILY_USAGE_LIMIT_EXCEEDED = "daily_usage_limit_exceeded"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    AGENT_INTERNAL_ERROR = "agent_internal_error"
    STEP_LIMIT_EXCEEDED = "step_limit_exceeded"
    SKILL_INTERRUPTED = "skill_interrupted"


# Default system messages
DEFAULT_SYSTEM_MESSAGES = {
    "service_fee_error": "Please lower this Agent's service fee to meet the allowed maximum.",
    "daily_usage_limit_exceeded": "This Agent has reached its free daily usage limit. Add credits to continue, or wait until tomorrow.",
    "insufficient_balance": "You don't have enough credits to complete this action.",
    "agent_internal_error": "Something went wrong. Please try again.",
    "step_limit_exceeded": "This Agent tried to process too many steps. Try again with @super for higher step limit.",
    "skill_interrupted": "You were interrupted after executing a skill. Please retry with caution to avoid repeating the skill.",
}

# In-memory cache for app settings
_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl = 180  # 3 minutes in seconds


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
                "free_quota": 480,
                "refill_amount": 20,
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
    free_quota: Annotated[
        Decimal,
        Field(
            default=Decimal("480"),
            description="Daily free credit quota for new users",
            ge=0,
        ),
    ]
    refill_amount: Annotated[
        Decimal,
        Field(
            default=Decimal("20"),
            description="Hourly refill amount for free credits",
            ge=0,
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

    @field_validator(
        "credit_per_usdc",
        "fee_platform_percentage",
        "fee_dev_percentage",
        "free_quota",
        "refill_amount",
    )
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
        """Get payment settings from the database with in-memory caching.

        The settings are cached in memory for 3 minutes.

        Returns:
            PaymentSettings: Payment settings
        """
        cache_key = "payment"
        current_time = time.time()

        # Check if we have cached data and it's still valid
        if cache_key in _cache:
            cache_entry = _cache[cache_key]
            if current_time - cache_entry["timestamp"] < _cache_ttl:
                return PaymentSettings(**cache_entry["data"])

        # If not in cache or cache is expired, get from database
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

            # Cache the settings in memory
            _cache[cache_key] = {
                "data": payment_settings.model_dump(mode="json"),
                "timestamp": current_time,
            }

            return payment_settings

    @staticmethod
    async def error_message(message_type: SystemMessageType) -> str:
        """Get error message from the database with in-memory caching, fallback to default.

        The settings are cached in memory for 3 minutes.

        Args:
            message_type: The SystemMessageType enum

        Returns:
            str: Error message from config or default message
        """
        cache_key = "errors"
        current_time = time.time()
        message_key = message_type.value

        # Check if we have cached data and it's still valid
        if cache_key in _cache:
            cache_entry = _cache[cache_key]
            if current_time - cache_entry["timestamp"] < _cache_ttl:
                errors_data = cache_entry["data"]
                if errors_data and message_key in errors_data:
                    return errors_data[message_key]
                # Return default message if not found in config
                return DEFAULT_SYSTEM_MESSAGES[message_key]

        # If not in cache or cache is expired, get from database
        async with get_session() as session:
            # Query the database for the errors settings
            stmt = select(AppSettingTable).where(AppSettingTable.key == "errors")
            setting = await session.scalar(stmt)

            # If settings don't exist, cache None
            errors_data = setting.value if setting else None

            # Cache the settings in memory
            _cache[cache_key] = {
                "data": errors_data,
                "timestamp": current_time,
            }

            # Return configured message if exists, otherwise return default
            if errors_data and message_key in errors_data:
                return errors_data[message_key]
            return DEFAULT_SYSTEM_MESSAGES[message_key]
