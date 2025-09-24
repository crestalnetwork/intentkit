import csv
import json
import logging
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Optional

from intentkit.models.app_setting import AppSetting
from intentkit.models.base import Base
from intentkit.models.db import get_session
from intentkit.models.redis import get_redis
from intentkit.utils.error import IntentKitLookUpError
from langchain.chat_models.base import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_credit_per_usdc = None
FOURPLACES = Decimal("0.0001")


def _parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"true", "1", "yes"}


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    value = value.strip()
    return int(value) if value else None


def _load_default_llm_models() -> dict[str, "LLMModelInfo"]:
    """Load default LLM models from a CSV file."""

    path = Path(__file__).with_name("llm.csv")
    if not path.exists():
        logger.warning("Default LLM CSV not found at %s", path)
        return {}

    defaults: dict[str, "LLMModelInfo"] = {}
    with path.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                timestamp = datetime.now(timezone.utc)
                model = LLMModelInfo(
                    id=row["id"],
                    name=row["name"],
                    provider=LLMProvider(row["provider"]),
                    enabled=_parse_bool(row.get("enabled")),
                    input_price=Decimal(row["input_price"]),
                    output_price=Decimal(row["output_price"]),
                    price_level=_parse_optional_int(row.get("price_level")),
                    context_length=int(row["context_length"]),
                    output_length=int(row["output_length"]),
                    intelligence=int(row["intelligence"]),
                    speed=int(row["speed"]),
                    supports_image_input=_parse_bool(row.get("supports_image_input")),
                    supports_skill_calls=_parse_bool(row.get("supports_skill_calls")),
                    supports_structured_output=_parse_bool(
                        row.get("supports_structured_output")
                    ),
                    has_reasoning=_parse_bool(row.get("has_reasoning")),
                    supports_search=_parse_bool(row.get("supports_search")),
                    supports_temperature=_parse_bool(row.get("supports_temperature")),
                    supports_frequency_penalty=_parse_bool(
                        row.get("supports_frequency_penalty")
                    ),
                    supports_presence_penalty=_parse_bool(
                        row.get("supports_presence_penalty")
                    ),
                    api_base=row.get("api_base", "").strip() or None,
                    timeout=int(row.get("timeout", "") or 180),
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            except Exception as exc:
                logger.error(
                    "Failed to load default LLM model %s: %s", row.get("id"), exc
                )
                continue
            defaults[model.id] = model

    return defaults


class LLMProvider(str, Enum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    XAI = "xai"
    ETERNAL = "eternal"
    REIGENT = "reigent"
    VENICE = "venice"

    def display_name(self) -> str:
        """Return user-friendly display name for the provider."""
        display_names = {
            self.OPENAI: "OpenAI",
            self.DEEPSEEK: "DeepSeek",
            self.XAI: "xAI",
            self.ETERNAL: "Others",
            self.REIGENT: "Others",
            self.VENICE: "Others",
        }
        return display_names.get(self, self.value)


class LLMModelInfoTable(Base):
    """Database table model for LLM model information."""

    __tablename__ = "llm_models"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    provider = Column(String, nullable=False)  # Stored as string enum value
    enabled = Column(Boolean, nullable=False, default=True)
    input_price = Column(
        Numeric(22, 4), nullable=False
    )  # Price per 1M input tokens in USD
    output_price = Column(
        Numeric(22, 4), nullable=False
    )  # Price per 1M output tokens in USD
    price_level = Column(Integer, nullable=True)  # Price level rating from 1-5
    context_length = Column(Integer, nullable=False)  # Maximum context length in tokens
    output_length = Column(Integer, nullable=False)  # Maximum output length in tokens
    intelligence = Column(Integer, nullable=False)  # Intelligence rating from 1-5
    speed = Column(Integer, nullable=False)  # Speed rating from 1-5
    supports_image_input = Column(Boolean, nullable=False, default=False)
    supports_skill_calls = Column(Boolean, nullable=False, default=False)
    supports_structured_output = Column(Boolean, nullable=False, default=False)
    has_reasoning = Column(Boolean, nullable=False, default=False)
    supports_search = Column(Boolean, nullable=False, default=False)
    supports_temperature = Column(Boolean, nullable=False, default=True)
    supports_frequency_penalty = Column(Boolean, nullable=False, default=True)
    supports_presence_penalty = Column(Boolean, nullable=False, default=True)
    api_base = Column(String, nullable=True)  # Custom API base URL
    timeout = Column(Integer, nullable=False, default=180)  # Default timeout in seconds
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


class LLMModelInfo(BaseModel):
    """Information about an LLM model."""

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        json_encoders={datetime: lambda v: v.isoformat(timespec="milliseconds")},
    )

    id: str
    name: str
    provider: LLMProvider
    enabled: bool = Field(default=True)
    input_price: Decimal  # Price per 1M input tokens in USD
    output_price: Decimal  # Price per 1M output tokens in USD
    price_level: Optional[int] = Field(
        default=None, ge=1, le=5
    )  # Price level rating from 1-5
    context_length: int  # Maximum context length in tokens
    output_length: int  # Maximum output length in tokens
    intelligence: int = Field(ge=1, le=5)  # Intelligence rating from 1-5
    speed: int = Field(ge=1, le=5)  # Speed rating from 1-5
    supports_image_input: bool = False  # Whether the model supports image inputs
    supports_skill_calls: bool = False  # Whether the model supports skill/tool calls
    supports_structured_output: bool = (
        False  # Whether the model supports structured output
    )
    has_reasoning: bool = False  # Whether the model has strong reasoning capabilities
    supports_search: bool = (
        False  # Whether the model supports native search functionality
    )
    supports_temperature: bool = (
        True  # Whether the model supports temperature parameter
    )
    supports_frequency_penalty: bool = (
        True  # Whether the model supports frequency_penalty parameter
    )
    supports_presence_penalty: bool = (
        True  # Whether the model supports presence_penalty parameter
    )
    api_base: Optional[str] = (
        None  # Custom API base URL if not using provider's default
    )
    timeout: int = 180  # Default timeout in seconds
    created_at: Annotated[
        datetime,
        Field(
            description="Timestamp when this data was created",
            default=datetime.now(timezone.utc),
        ),
    ]
    updated_at: Annotated[
        datetime,
        Field(
            description="Timestamp when this data was updated",
            default=datetime.now(timezone.utc),
        ),
    ]

    @staticmethod
    async def get(model_id: str) -> "LLMModelInfo":
        """Get a model by ID with Redis caching.

        The model info is cached in Redis for 3 minutes.

        Args:
            model_id: ID of the model to retrieve

        Returns:
            LLMModelInfo: The model info if found, None otherwise
        """
        try:
            has_redis = True
            # Redis cache key for model info
            cache_key = f"intentkit:llm_model:{model_id}"
            cache_ttl = 180  # 3 minutes in seconds

            # Try to get from Redis cache first
            redis = get_redis()
            cached_data = await redis.get(cache_key)

            if cached_data:
                # If found in cache, deserialize and return
                try:
                    return LLMModelInfo.model_validate_json(cached_data)
                except (json.JSONDecodeError, TypeError):
                    # If cache is corrupted, invalidate it
                    await redis.delete(cache_key)
        except Exception:
            has_redis = False
            logger.debug("No redis when get model info")

        # If not in cache or cache is invalid, get from database
        async with get_session() as session:
            # Query the database for the model
            stmt = select(LLMModelInfoTable).where(LLMModelInfoTable.id == model_id)
            model = await session.scalar(stmt)

            # If model exists in database, convert to LLMModelInfo model and cache it
            if model:
                # Convert provider string to enum
                model_info = LLMModelInfo.model_validate(model)

                # Cache the model in Redis
                if has_redis:
                    await redis.set(
                        cache_key,
                        model_info.model_dump_json(),
                        ex=cache_ttl,
                    )

                return model_info

        # If not found in database, check AVAILABLE_MODELS
        if model_id in AVAILABLE_MODELS:
            model_info = AVAILABLE_MODELS[model_id]

            # Cache the model in Redis
            if has_redis:
                await redis.set(cache_key, model_info.model_dump_json(), ex=cache_ttl)

            return model_info

        # Not found anywhere
        raise IntentKitLookUpError(f"Model {model_id} not found")

    @classmethod
    async def get_all(cls, session: AsyncSession | None = None) -> list["LLMModelInfo"]:
        """Return all models merged from defaults and database overrides."""

        if session is None:
            async with get_session() as db:
                return await cls.get_all(session=db)

        models: dict[str, "LLMModelInfo"] = {
            model_id: model.model_copy(deep=True)
            for model_id, model in AVAILABLE_MODELS.items()
        }

        result = await session.execute(select(LLMModelInfoTable))
        for row in result.scalars():
            model_info = cls.model_validate(row)
            models[model_info.id] = model_info

        return list(models.values())

    async def calculate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        global _credit_per_usdc
        if not _credit_per_usdc:
            _credit_per_usdc = (await AppSetting.payment()).credit_per_usdc
        """Calculate the cost for a given number of tokens."""
        input_cost = (
            _credit_per_usdc
            * Decimal(input_tokens)
            * self.input_price
            / Decimal(1000000)
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        output_cost = (
            _credit_per_usdc
            * Decimal(output_tokens)
            * self.output_price
            / Decimal(1000000)
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        return (input_cost + output_cost).quantize(FOURPLACES, rounding=ROUND_HALF_UP)


# Default models loaded from CSV
AVAILABLE_MODELS = _load_default_llm_models()


class LLMModel(BaseModel):
    """Base model for LLM configuration."""

    model_name: str
    temperature: float = 0.7
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    info: LLMModelInfo

    async def model_info(self) -> LLMModelInfo:
        """Get the model information with caching.

        First tries to get from cache, then database, then default models loaded from CSV.
        Raises ValueError if model is not found anywhere.
        """
        model_info = await LLMModelInfo.get(self.model_name)
        return model_info

    # This will be implemented by subclasses to return the appropriate LLM instance
    async def create_instance(self, config: Any) -> BaseChatModel:
        """Create and return the LLM instance based on the configuration."""
        raise NotImplementedError("Subclasses must implement create_instance")

    async def get_token_limit(self) -> int:
        """Get the token limit for this model."""
        info = await self.model_info()
        return info.context_length

    async def calculate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        """Calculate the cost for a given number of tokens."""
        info = await self.model_info()
        return await info.calculate_cost(input_tokens, output_tokens)


class OpenAILLM(LLMModel):
    """OpenAI LLM configuration."""

    async def create_instance(self, config: Any) -> BaseChatModel:
        """Create and return a ChatOpenAI instance."""
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        kwargs = {
            "model_name": self.model_name,
            "openai_api_key": config.openai_api_key,
            "timeout": info.timeout,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        if info.api_base:
            kwargs["openai_api_base"] = info.api_base

        if self.model_name.startswith("gpt-5"):
            kwargs["reasoning_effort"] = "minimal"

        logger.debug(f"Creating ChatOpenAI instance with kwargs: {kwargs}")

        return ChatOpenAI(**kwargs)


class DeepseekLLM(LLMModel):
    """Deepseek LLM configuration."""

    async def create_instance(self, config: Any) -> BaseChatModel:
        """Create and return a ChatDeepseek instance."""

        from langchain_deepseek import ChatDeepSeek

        info = await self.model_info()

        kwargs = {
            "model": self.model_name,
            "api_key": config.deepseek_api_key,
            "timeout": info.timeout,
            "max_retries": 3,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        if info.api_base:
            kwargs["api_base"] = info.api_base

        return ChatDeepSeek(**kwargs)


class XAILLM(LLMModel):
    """XAI (Grok) LLM configuration."""

    async def create_instance(self, config: Any) -> BaseChatModel:
        """Create and return a ChatXAI instance."""

        from langchain_xai import ChatXAI

        info = await self.model_info()

        kwargs = {
            "model_name": self.model_name,
            "xai_api_key": config.xai_api_key,
            "timeout": info.timeout,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        if self.model_name in ["grok-3", "grok-3-mini"]:
            kwargs["search_parameters"] = {"mode": "auto"}

        return ChatXAI(**kwargs)


class EternalLLM(LLMModel):
    """Eternal AI LLM configuration."""

    async def create_instance(self, config: Any) -> BaseChatModel:
        """Create and return a ChatOpenAI instance configured for Eternal AI."""
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        # Override model name for Eternal AI
        actual_model = "unsloth/Llama-3.3-70B-Instruct-bnb-4bit"

        kwargs = {
            "model_name": actual_model,
            "openai_api_key": config.eternal_api_key,
            "openai_api_base": info.api_base,
            "timeout": info.timeout,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        return ChatOpenAI(**kwargs)


class ReigentLLM(LLMModel):
    """Reigent LLM configuration."""

    async def create_instance(self, config: Any) -> BaseChatModel:
        """Create and return a ChatOpenAI instance configured for Reigent."""
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        kwargs = {
            "openai_api_key": config.reigent_api_key,
            "openai_api_base": info.api_base,
            "timeout": info.timeout,
            "model_kwargs": {
                # Override any specific parameters required for Reigent API
                # The Reigent API requires 'tools' instead of 'functions' and might have some specific formatting requirements
            },
        }

        return ChatOpenAI(**kwargs)


class VeniceLLM(LLMModel):
    """Venice LLM configuration."""

    async def create_instance(self, config: Any) -> BaseChatModel:
        """Create and return a ChatOpenAI instance configured for Venice."""
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        kwargs = {
            "openai_api_key": config.venice_api_key,
            "openai_api_base": info.api_base,
            "timeout": info.timeout,
        }

        return ChatOpenAI(**kwargs)


# Factory function to create the appropriate LLM model based on the model name
async def create_llm_model(
    model_name: str,
    temperature: float = 0.7,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
) -> LLMModel:
    """
    Create an LLM model instance based on the model name.

    Args:
        model_name: The name of the model to use
        temperature: The temperature parameter for the model
        frequency_penalty: The frequency penalty parameter for the model
        presence_penalty: The presence penalty parameter for the model

    Returns:
        An instance of a subclass of LLMModel
    """
    info = await LLMModelInfo.get(model_name)

    base_params = {
        "model_name": model_name,
        "temperature": temperature,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "info": info,
    }

    provider = info.provider

    if provider == LLMProvider.DEEPSEEK:
        return DeepseekLLM(**base_params)
    elif provider == LLMProvider.XAI:
        return XAILLM(**base_params)
    elif provider == LLMProvider.ETERNAL:
        return EternalLLM(**base_params)
    elif provider == LLMProvider.REIGENT:
        return ReigentLLM(**base_params)
    elif provider == LLMProvider.VENICE:
        return VeniceLLM(**base_params)
    else:
        # Default to OpenAI
        return OpenAILLM(**base_params)
