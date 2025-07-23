import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Dict, Optional

from fastapi import HTTPException
from intentkit.models.base import Base
from intentkit.models.db import get_session
from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Numeric,
    String,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB

logger = logging.getLogger(__name__)


class AgentDataTable(Base):
    """Agent data model for database storage of additional data related to the agent."""

    __tablename__ = "agent_data"

    id = Column(String, primary_key=True, comment="Same as Agent.id")
    evm_wallet_address = Column(String, nullable=True, comment="EVM wallet address")
    solana_wallet_address = Column(
        String, nullable=True, comment="Solana wallet address"
    )
    cdp_wallet_data = Column(String, nullable=True, comment="CDP wallet data")
    twitter_id = Column(String, nullable=True, comment="Twitter user ID")
    twitter_username = Column(String, nullable=True, comment="Twitter username")
    twitter_name = Column(String, nullable=True, comment="Twitter display name")
    twitter_access_token = Column(String, nullable=True, comment="Twitter access token")
    twitter_access_token_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Twitter access token expiration time",
    )
    twitter_refresh_token = Column(
        String, nullable=True, comment="Twitter refresh token"
    )
    twitter_self_key_refreshed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Twitter self-key userinfo last refresh time",
    )
    twitter_is_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the Twitter account is verified",
    )
    telegram_id = Column(String, nullable=True, comment="Telegram user ID")
    telegram_username = Column(String, nullable=True, comment="Telegram username")
    telegram_name = Column(String, nullable=True, comment="Telegram display name")
    error_message = Column(String, nullable=True, comment="Last error message")
    api_key = Column(
        String, nullable=True, unique=True, comment="API key for the agent"
    )
    api_key_public = Column(
        String, nullable=True, unique=True, comment="Public API key for the agent"
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the agent data was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the agent data was last updated",
    )


class AgentData(BaseModel):
    """Agent data model for storing additional data related to the agent."""

    model_config = ConfigDict(from_attributes=True)

    id: Annotated[
        str,
        PydanticField(
            description="Same as Agent.id",
        ),
    ]
    evm_wallet_address: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="EVM wallet address",
        ),
    ] = None
    solana_wallet_address: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Solana wallet address",
        ),
    ] = None
    cdp_wallet_data: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="CDP wallet data",
        ),
    ] = None
    twitter_id: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Twitter user ID",
        ),
    ] = None
    twitter_username: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Twitter username",
        ),
    ] = None
    twitter_name: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Twitter display name",
        ),
    ] = None
    twitter_access_token: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Twitter access token",
        ),
    ] = None
    twitter_access_token_expires_at: Annotated[
        Optional[datetime],
        PydanticField(
            default=None,
            description="Twitter access token expiration time",
        ),
    ] = None
    twitter_refresh_token: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Twitter refresh token",
        ),
    ] = None
    twitter_self_key_refreshed_at: Annotated[
        Optional[datetime],
        PydanticField(
            default=None,
            description="Twitter self-key userinfo last refresh time",
        ),
    ] = None
    twitter_is_verified: Annotated[
        bool,
        PydanticField(
            default=False,
            description="Whether the Twitter account is verified",
        ),
    ] = None
    telegram_id: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Telegram user ID",
        ),
    ] = None
    telegram_username: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Telegram username",
        ),
    ] = None
    telegram_name: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Telegram display name",
        ),
    ] = None
    error_message: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Last error message",
        ),
    ] = None
    api_key: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="API key for the agent",
        ),
    ] = None
    api_key_public: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Public API key for the agent",
        ),
    ] = None
    created_at: Annotated[
        datetime,
        PydanticField(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp when the agent data was created",
        ),
    ]
    updated_at: Annotated[
        datetime,
        PydanticField(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp when the agent data was last updated",
        ),
    ]

    @classmethod
    async def get(cls, agent_id: str) -> "AgentData":
        """Get agent data by ID.

        Args:
            agent_id: Agent ID

        Returns:
            AgentData if found, None otherwise

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            item = await db.get(AgentDataTable, agent_id)
            if item:
                return cls.model_validate(item)
            return cls.model_construct(id=agent_id)

    @classmethod
    async def get_by_api_key(cls, api_key: str) -> Optional["AgentData"]:
        """Get agent data by API key.

        Args:
            api_key: API key (sk- for private, pk- for public)

        Returns:
            AgentData if found, None otherwise

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            if api_key.startswith("sk-"):
                # Search in api_key field for private keys
                result = await db.execute(
                    select(AgentDataTable).where(AgentDataTable.api_key == api_key)
                )
            elif api_key.startswith("pk-"):
                # Search in api_key_public field for public keys
                result = await db.execute(
                    select(AgentDataTable).where(
                        AgentDataTable.api_key_public == api_key
                    )
                )
            else:
                # Invalid key format
                return None

            item = result.scalar_one_or_none()
            if item:
                return cls.model_validate(item)
            return None

    async def save(self) -> None:
        """Save or update agent data.

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            existing = await db.get(AgentDataTable, self.id)
            if existing:
                # Update existing record
                for field, value in self.model_dump(exclude_unset=True).items():
                    setattr(existing, field, value)
                db.add(existing)
            else:
                # Create new record
                db_agent_data = AgentDataTable(**self.model_dump())
                db.add(db_agent_data)

            await db.commit()

    @staticmethod
    async def patch(id: str, data: dict) -> "AgentData":
        """Update agent data.

        Args:
            id: ID of the agent
            data: Dictionary containing fields to update

        Returns:
            Updated agent data

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            agent_data = await db.get(AgentDataTable, id)
            if not agent_data:
                agent_data = AgentDataTable(id=id, **data)
                db.add(agent_data)
            else:
                for key, value in data.items():
                    setattr(agent_data, key, value)
            await db.commit()
            await db.refresh(agent_data)
            return AgentData.model_validate(agent_data)


class AgentPluginDataTable(Base):
    """Database model for storing plugin-specific data for agents.

    This model uses a composite primary key of (agent_id, plugin, key) to store
    plugin-specific data for agents in a flexible way.

    Attributes:
        agent_id: ID of the agent this data belongs to
        plugin: Name of the plugin this data is for
        key: Key for this specific piece of data
        data: JSON data stored for this key
    """

    __tablename__ = "agent_plugin_data"

    agent_id = Column(String, primary_key=True)
    plugin = Column(String, primary_key=True)
    key = Column(String, primary_key=True)
    data = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
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


class AgentPluginData(BaseModel):
    """Model for storing plugin-specific data for agents.

    This model uses a composite primary key of (agent_id, plugin, key) to store
    plugin-specific data for agents in a flexible way.

    Attributes:
        agent_id: ID of the agent this data belongs to
        plugin: Name of the plugin this data is for
        key: Key for this specific piece of data
        data: JSON data stored for this key
    """

    model_config = ConfigDict(from_attributes=True)

    agent_id: Annotated[
        str,
        PydanticField(description="ID of the agent this data belongs to"),
    ]
    plugin: Annotated[
        str,
        PydanticField(description="Name of the plugin this data is for"),
    ]
    key: Annotated[
        str,
        PydanticField(description="Key for this specific piece of data"),
    ]
    data: Annotated[
        Dict[str, Any],
        PydanticField(default=None, description="JSON data stored for this key"),
    ]
    created_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when this data was created",
            default_factory=lambda: datetime.now(timezone.utc),
        ),
    ]
    updated_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when this data was last updated",
            default_factory=lambda: datetime.now(timezone.utc),
        ),
    ]

    @classmethod
    async def get(
        cls, agent_id: str, plugin: str, key: str
    ) -> Optional["AgentPluginData"]:
        """Get plugin data for an agent.

        Args:
            agent_id: ID of the agent
            plugin: Name of the plugin
            key: Data key

        Returns:
            AgentPluginData if found, None otherwise

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            item = await db.scalar(
                select(AgentPluginDataTable).where(
                    AgentPluginDataTable.agent_id == agent_id,
                    AgentPluginDataTable.plugin == plugin,
                    AgentPluginDataTable.key == key,
                )
            )
            if item:
                return cls.model_validate(item)
            return None

    async def save(self) -> None:
        """Save or update plugin data.

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            plugin_data = await db.scalar(
                select(AgentPluginDataTable).where(
                    AgentPluginDataTable.agent_id == self.agent_id,
                    AgentPluginDataTable.plugin == self.plugin,
                    AgentPluginDataTable.key == self.key,
                )
            )

            if plugin_data:
                # Update existing record
                plugin_data.data = self.data
                db.add(plugin_data)
            else:
                # Create new record
                plugin_data = AgentPluginDataTable(
                    agent_id=self.agent_id,
                    plugin=self.plugin,
                    key=self.key,
                    data=self.data,
                )
                db.add(plugin_data)

            await db.commit()
            await db.refresh(plugin_data)

            # Refresh the model with updated data
            self.model_validate(plugin_data)


class AgentQuotaTable(Base):
    """AgentQuota database table model."""

    __tablename__ = "agent_quotas"

    id = Column(String, primary_key=True)
    plan = Column(String, default="self-hosted")
    message_count_total = Column(BigInteger, default=0)
    message_limit_total = Column(BigInteger, default=99999999)
    message_count_monthly = Column(BigInteger, default=0)
    message_limit_monthly = Column(BigInteger, default=99999999)
    message_count_daily = Column(BigInteger, default=0)
    message_limit_daily = Column(BigInteger, default=99999999)
    last_message_time = Column(DateTime(timezone=True), default=None, nullable=True)
    autonomous_count_total = Column(BigInteger, default=0)
    autonomous_limit_total = Column(BigInteger, default=99999999)
    autonomous_count_monthly = Column(BigInteger, default=0)
    autonomous_limit_monthly = Column(BigInteger, default=99999999)
    last_autonomous_time = Column(DateTime(timezone=True), default=None, nullable=True)
    twitter_count_total = Column(BigInteger, default=0)
    twitter_limit_total = Column(BigInteger, default=99999999)
    twitter_count_monthly = Column(BigInteger, default=0)
    twitter_limit_monthly = Column(BigInteger, default=99999999)
    twitter_count_daily = Column(BigInteger, default=0)
    twitter_limit_daily = Column(BigInteger, default=99999999)
    last_twitter_time = Column(DateTime(timezone=True), default=None, nullable=True)
    free_income_daily = Column(Numeric(22, 4), default=0)
    avg_action_cost = Column(Numeric(22, 4), default=0)
    min_action_cost = Column(Numeric(22, 4), default=0)
    max_action_cost = Column(Numeric(22, 4), default=0)
    low_action_cost = Column(Numeric(22, 4), default=0)
    medium_action_cost = Column(Numeric(22, 4), default=0)
    high_action_cost = Column(Numeric(22, 4), default=0)
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


class AgentQuota(BaseModel):
    """AgentQuota model."""

    model_config = ConfigDict(from_attributes=True)

    id: Annotated[
        str, PydanticField(description="ID of the agent this quota belongs to")
    ]
    plan: Annotated[
        str, PydanticField(default="self-hosted", description="Agent plan name")
    ]
    message_count_total: Annotated[
        int, PydanticField(default=0, description="Total message count")
    ]
    message_limit_total: Annotated[
        int, PydanticField(default=99999999, description="Total message limit")
    ]
    message_count_monthly: Annotated[
        int, PydanticField(default=0, description="Monthly message count")
    ]
    message_limit_monthly: Annotated[
        int, PydanticField(default=99999999, description="Monthly message limit")
    ]
    message_count_daily: Annotated[
        int, PydanticField(default=0, description="Daily message count")
    ]
    message_limit_daily: Annotated[
        int, PydanticField(default=99999999, description="Daily message limit")
    ]
    last_message_time: Annotated[
        Optional[datetime],
        PydanticField(default=None, description="Last message timestamp"),
    ]
    autonomous_count_total: Annotated[
        int, PydanticField(default=0, description="Total autonomous operations count")
    ]
    autonomous_limit_total: Annotated[
        int,
        PydanticField(
            default=99999999, description="Total autonomous operations limit"
        ),
    ]
    autonomous_count_monthly: Annotated[
        int, PydanticField(default=0, description="Monthly autonomous operations count")
    ]
    autonomous_limit_monthly: Annotated[
        int,
        PydanticField(
            default=99999999, description="Monthly autonomous operations limit"
        ),
    ]
    autonomous_count_daily: Annotated[
        int, PydanticField(default=0, description="Daily autonomous operations count")
    ]
    autonomous_limit_daily: Annotated[
        int,
        PydanticField(
            default=99999999, description="Daily autonomous operations limit"
        ),
    ]
    last_autonomous_time: Annotated[
        Optional[datetime],
        PydanticField(default=None, description="Last autonomous operation timestamp"),
    ]
    twitter_count_total: Annotated[
        int, PydanticField(default=0, description="Total Twitter operations count")
    ]
    twitter_limit_total: Annotated[
        int,
        PydanticField(default=99999999, description="Total Twitter operations limit"),
    ]
    twitter_count_monthly: Annotated[
        int, PydanticField(default=0, description="Monthly Twitter operations count")
    ]
    twitter_limit_monthly: Annotated[
        int,
        PydanticField(default=99999999, description="Monthly Twitter operations limit"),
    ]
    twitter_count_daily: Annotated[
        int, PydanticField(default=0, description="Daily Twitter operations count")
    ]
    twitter_limit_daily: Annotated[
        int,
        PydanticField(default=99999999, description="Daily Twitter operations limit"),
    ]
    last_twitter_time: Annotated[
        Optional[datetime],
        PydanticField(default=None, description="Last Twitter operation timestamp"),
    ]
    free_income_daily: Annotated[
        Decimal,
        PydanticField(default=0, description="Daily free income amount"),
    ]
    avg_action_cost: Annotated[
        Decimal,
        PydanticField(default=0, description="Average cost per action"),
    ]
    max_action_cost: Annotated[
        Decimal,
        PydanticField(default=0, description="Maximum cost per action"),
    ]
    min_action_cost: Annotated[
        Decimal,
        PydanticField(default=0, description="Minimum cost per action"),
    ]
    high_action_cost: Annotated[
        Decimal,
        PydanticField(default=0, description="High expected action cost"),
    ]
    medium_action_cost: Annotated[
        Decimal,
        PydanticField(default=0, description="Medium expected action cost"),
    ]
    low_action_cost: Annotated[
        Decimal,
        PydanticField(default=0, description="Low expected action cost"),
    ]
    created_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when this quota was created",
            default_factory=lambda: datetime.now(timezone.utc),
        ),
    ]
    updated_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when this quota was last updated",
            default_factory=lambda: datetime.now(timezone.utc),
        ),
    ]

    @classmethod
    async def get(cls, agent_id: str) -> "AgentQuota":
        """Get agent quota by id, if not exists, create a new one.

        Args:
            agent_id: Agent ID

        Returns:
            AgentQuota: The agent's quota object

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            quota_record = await db.get(AgentQuotaTable, agent_id)
            if not quota_record:
                # Create new record
                quota_record = AgentQuotaTable(
                    id=agent_id,
                )
                db.add(quota_record)
                await db.commit()
                await db.refresh(quota_record)

            return cls.model_validate(quota_record)

    def has_message_quota(self) -> bool:
        """Check if the agent has message quota.

        Returns:
            bool: True if the agent has quota, False otherwise
        """
        # Check total limit
        if self.message_count_total >= self.message_limit_total:
            return False
        # Check monthly limit
        if self.message_count_monthly >= self.message_limit_monthly:
            return False
        # Check daily limit
        if self.message_count_daily >= self.message_limit_daily:
            return False
        return True

    def has_autonomous_quota(self) -> bool:
        """Check if the agent has autonomous quota.

        Returns:
            bool: True if the agent has quota, False otherwise
        """
        # Check total limit
        if self.autonomous_count_total >= self.autonomous_limit_total:
            return False
        # Check monthly limit
        if self.autonomous_count_monthly >= self.autonomous_limit_monthly:
            return False
        return True

    def has_twitter_quota(self) -> bool:
        """Check if the agent has twitter quota.

        Returns:
            bool: True if the agent has quota, False otherwise
        """
        # Check total limit
        if self.twitter_count_total >= self.twitter_limit_total:
            return False
        # Check daily limit
        if self.twitter_count_daily >= self.twitter_limit_daily:
            return False
        return True

    @staticmethod
    async def add_free_income_in_session(session, id: str, amount: Decimal) -> None:
        """Add free income to an agent's quota directly in the database.

        Args:
            session: SQLAlchemy session
            id: Agent ID
            amount: Amount to add to free_income_daily

        Raises:
            HTTPException: If there are database errors
        """
        try:
            # Check if the record exists using session.get
            quota_record = await session.get(AgentQuotaTable, id)

            if not quota_record:
                # Create new record if it doesn't exist
                quota_record = AgentQuotaTable(id=id, free_income_daily=amount)
                session.add(quota_record)
            else:
                # Use update statement with func to directly add the amount
                from sqlalchemy import update

                stmt = update(AgentQuotaTable).where(AgentQuotaTable.id == id)
                stmt = stmt.values(
                    free_income_daily=func.coalesce(
                        AgentQuotaTable.free_income_daily, 0
                    )
                    + amount
                )
                await session.execute(stmt)
        except Exception as e:
            logger.error(f"Error adding free income: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def add_message(self) -> None:
        """Add a message to the agent's message count."""
        async with get_session() as db:
            quota_record = await db.get(AgentQuotaTable, self.id)

            if quota_record:
                # Update record
                quota_record.message_count_total += 1
                quota_record.message_count_monthly += 1
                quota_record.message_count_daily += 1
                quota_record.last_message_time = datetime.now(timezone.utc)
                db.add(quota_record)
                await db.commit()

                # Update this instance
                await db.refresh(quota_record)
                self.message_count_total = quota_record.message_count_total
                self.message_count_monthly = quota_record.message_count_monthly
                self.message_count_daily = quota_record.message_count_daily
                self.last_message_time = quota_record.last_message_time
                self.updated_at = quota_record.updated_at

    async def add_autonomous(self) -> None:
        """Add an autonomous operation to the agent's autonomous count."""
        async with get_session() as db:
            quota_record = await db.get(AgentQuotaTable, self.id)
            if quota_record:
                # Update record
                quota_record.autonomous_count_total += 1
                quota_record.autonomous_count_monthly += 1
                quota_record.last_autonomous_time = datetime.now(timezone.utc)
                db.add(quota_record)
                await db.commit()

                # Update this instance
                await db.refresh(quota_record)
                self.model_validate(quota_record)

    async def add_twitter_message(self) -> None:
        """Add a twitter message to the agent's twitter count.

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            quota_record = await db.get(AgentQuotaTable, self.id)

            if quota_record:
                # Update record
                quota_record.twitter_count_total += 1
                quota_record.twitter_count_daily += 1
                quota_record.last_twitter_time = datetime.now(timezone.utc)
                db.add(quota_record)
                await db.commit()

                # Update this instance
                await db.refresh(quota_record)
                self.model_validate(quota_record)

    @staticmethod
    async def reset_daily_quotas():
        """Reset daily quotas for all agents at UTC 00:00.
        Resets message_count_daily and twitter_count_daily to 0.
        """
        from sqlalchemy import update

        async with get_session() as session:
            stmt = update(AgentQuotaTable).values(
                message_count_daily=0,
                twitter_count_daily=0,
                free_income_daily=0,
            )
            await session.execute(stmt)
            await session.commit()

    @staticmethod
    async def reset_monthly_quotas():
        """Reset monthly quotas for all agents at the start of each month.
        Resets message_count_monthly and autonomous_count_monthly to 0.
        """
        from sqlalchemy import update

        async with get_session() as session:
            stmt = update(AgentQuotaTable).values(
                message_count_monthly=0, autonomous_count_monthly=0
            )
            await session.execute(stmt)
            await session.commit()
