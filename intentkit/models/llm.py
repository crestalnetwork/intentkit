import csv
import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Callable, ClassVar

from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from typing_extensions import override

from intentkit.config.base import Base
from intentkit.config.config import config
from intentkit.config.db import get_session
from intentkit.config.redis import get_redis
from intentkit.models.app_setting import AppSetting
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

# Process-lifetime cache for the credit-per-USDC rate fetched from AppSetting.
# This value is loaded on first use and never refreshed until the process restarts,
# which is acceptable because rate changes are infrequent and a restart picks them up.
credit_per_usdc = None
FOURPLACES = Decimal("0.0001")


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"true", "1", "yes"}


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    return int(value) if value else None


def _parse_optional_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    value = value.strip()
    return Decimal(value) if value else None


def load_default_llm_models() -> dict[str, "LLMModelInfo"]:
    """Load default LLM models from a CSV file.

    Models are keyed by ``{provider}:{id}`` so that the same model ID from
    different providers (e.g. ``deepseek-chat`` via DeepSeek *and* OpenRouter)
    is preserved as separate entries.
    """

    path = Path(__file__).with_name("llm.csv")
    if not path.exists():
        logger.warning("Default LLM CSV not found at %s", path)
        return {}

    defaults: dict[str, LLMModelInfo] = {}
    with path.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                row_id = row.get("id")
                if not row_id:
                    continue

                timestamp = datetime.now(UTC)
                provider_val = row.get("provider", "")
                if not provider_val:
                    continue
                provider = LLMProvider(provider_val)

                # Use a dict to gather attributes for cleaner instantiation
                attrs: dict[str, Any] = {
                    "id": row_id,
                    "name": row.get("name") or row_id,
                    "provider": provider,
                    "enabled": _parse_bool(row.get("enabled")),
                    "input_price": Decimal(row.get("input_price", "0")),
                    "cached_input_price": _parse_optional_decimal(
                        row.get("cached_input_price")
                    ),
                    "output_price": Decimal(row.get("output_price", "0")),
                    "price_level": _parse_optional_int(row.get("price_level")),
                    "context_length": int(row.get("context_length") or 0),
                    "output_length": int(row.get("output_length") or 0),
                    "intelligence": int(row.get("intelligence") or 1),
                    "speed": int(row.get("speed") or 1),
                    "supports_image_input": _parse_bool(
                        row.get("supports_image_input")
                    ),
                    "reasoning_effort": row.get("reasoning_effort", "").strip() or None,
                    "supports_temperature": _parse_bool(
                        row.get("supports_temperature")
                    ),
                    "supports_frequency_penalty": _parse_bool(
                        row.get("supports_frequency_penalty")
                    ),
                    "supports_presence_penalty": _parse_bool(
                        row.get("supports_presence_penalty")
                    ),
                    "timeout": int(row.get("timeout") or 180),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
                model = LLMModelInfo(**attrs)
                if not model.enabled:
                    continue
                if not model.provider.is_configured:
                    continue
            except Exception as exc:
                logger.error(
                    "Failed to load default LLM model %s: %s", row.get("id"), exc
                )
                continue
            # Key by provider:id so the same model from different providers is kept
            key = f"{provider.value}:{row_id}"
            defaults[key] = model

    # Load OpenAI Compatible models from config (not CSV)
    if (
        config.openai_compatible_api_key
        and config.openai_compatible_base_url
        and config.openai_compatible_model
    ):
        timestamp = datetime.now(UTC)
        provider = LLMProvider.OPENAI_COMPATIBLE
        base_attrs: dict[str, Any] = {
            "provider": provider,
            "enabled": True,
            "input_price": Decimal("0"),
            "output_price": Decimal("0"),
            "context_length": 200000,
            "output_length": 64000,
            "supports_image_input": False,
            "supports_temperature": True,
            "supports_frequency_penalty": True,
            "supports_presence_penalty": True,
            "timeout": 300,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        model_id = config.openai_compatible_model
        model = LLMModelInfo(
            id=model_id,
            name=model_id,
            intelligence=3,
            speed=3,
            reasoning_effort="high",
            **base_attrs,
        )
        defaults[f"{provider.value}:{model_id}"] = model

        if config.openai_compatible_model_lite:
            lite_id = config.openai_compatible_model_lite
            lite_model = LLMModelInfo(
                id=lite_id,
                name=lite_id,
                intelligence=2,
                speed=4,
                reasoning_effort=None,
                **base_attrs,
            )
            defaults[f"{provider.value}:{lite_id}"] = lite_model

    # Load Anthropic Compatible models from config (not CSV)
    if (
        config.anthropic_compatible_api_key
        and config.anthropic_compatible_base_url
        and config.anthropic_compatible_model
    ):
        timestamp = datetime.now(UTC)
        provider = LLMProvider.ANTHROPIC_COMPATIBLE
        base_attrs = {
            "provider": provider,
            "enabled": True,
            "input_price": Decimal("0"),
            "output_price": Decimal("0"),
            "context_length": 200000,
            "output_length": 64000,
            "supports_image_input": False,
            "supports_temperature": True,
            "supports_frequency_penalty": False,
            "supports_presence_penalty": False,
            "timeout": 300,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        model_id = config.anthropic_compatible_model
        model = LLMModelInfo(
            id=model_id,
            name=model_id,
            intelligence=3,
            speed=3,
            reasoning_effort="high",
            **base_attrs,
        )
        defaults[f"{provider.value}:{model_id}"] = model

        if config.anthropic_compatible_model_lite:
            lite_id = config.anthropic_compatible_model_lite
            lite_model = LLMModelInfo(
                id=lite_id,
                name=lite_id,
                intelligence=2,
                speed=4,
                reasoning_effort=None,
                **base_attrs,
            )
            defaults[f"{provider.value}:{lite_id}"] = lite_model

    return defaults


class LLMProvider(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"
    XAI = "xai"
    OPENROUTER = "openrouter"
    MINIMAX = "minimax"
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC_COMPATIBLE = "anthropic_compatible"

    @property
    def is_configured(self) -> bool:
        """Check if the provider is configured with an API key."""
        config_map = {
            self.OPENAI: bool(config.openai_api_key),
            self.GOOGLE: bool(config.google_api_key),
            self.DEEPSEEK: bool(config.deepseek_api_key),
            self.XAI: bool(config.xai_api_key),
            self.OPENROUTER: bool(config.openrouter_api_key),
            self.MINIMAX: bool(config.minimax_api_key),
            self.OLLAMA: True,  # Ollama usually doesn't need a key
            self.OPENAI_COMPATIBLE: bool(
                config.openai_compatible_api_key
                and config.openai_compatible_base_url
                and config.openai_compatible_model
            ),
            self.ANTHROPIC_COMPATIBLE: bool(
                config.anthropic_compatible_api_key
                and config.anthropic_compatible_base_url
                and config.anthropic_compatible_model
            ),
        }
        return config_map.get(self, False)

    def display_name(self) -> str:
        """Return user-friendly display name for the provider."""
        display_names = {
            self.OPENAI: "OpenAI",
            self.GOOGLE: "Google",
            self.DEEPSEEK: "DeepSeek",
            self.XAI: "xAI",
            self.OPENROUTER: "OpenRouter",
            self.MINIMAX: "MiniMax",
            self.OLLAMA: "Ollama",
            self.OPENAI_COMPATIBLE: config.openai_compatible_provider,
            self.ANTHROPIC_COMPATIBLE: config.anthropic_compatible_provider,
        }
        return display_names.get(self, self.value)


class LLMModelInfoTable(Base):
    """Database table model for LLM model information."""

    __tablename__: str = "llm_models"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)  # Stored as enum
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    input_price: Mapped[Decimal] = mapped_column(
        Numeric(22, 4), nullable=False
    )  # Price per 1M input tokens in USD
    cached_input_price: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4), nullable=True
    )  # Price per 1M cached input tokens in USD
    output_price: Mapped[Decimal] = mapped_column(
        Numeric(22, 4), nullable=False
    )  # Price per 1M output tokens in USD
    price_level: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Price level rating
    context_length: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Context length
    output_length: Mapped[int] = mapped_column(Integer, nullable=False)  # Output length
    intelligence: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Intelligence rating
    speed: Mapped[int] = mapped_column(Integer, nullable=False)  # Speed rating
    supports_image_input: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    reasoning_effort: Mapped[str | None] = mapped_column(String, nullable=True)
    supports_temperature: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    supports_frequency_penalty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    supports_presence_penalty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    timeout: Mapped[int] = mapped_column(
        Integer, nullable=False, default=180
    )  # Timeout seconds
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


class LLMModelInfo(BaseModel):
    """Information about an LLM model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        from_attributes=True,
    )

    id: str
    name: str
    provider: LLMProvider
    enabled: bool = Field(default=True)
    input_price: Decimal  # Price per 1M input tokens in USD
    cached_input_price: Decimal | None = None  # Price per 1M cached input tokens in USD
    output_price: Decimal  # Price per 1M output tokens in USD
    price_level: int | None = Field(
        default=None, ge=1, le=5
    )  # Price level rating from 1-5
    context_length: int  # Maximum context length in tokens
    output_length: int  # Maximum output length in tokens
    intelligence: int = Field(ge=1, le=5)  # Intelligence rating from 1-5
    speed: int = Field(ge=1, le=5)  # Speed rating from 1-5
    supports_image_input: bool = False  # Whether the model supports image inputs
    reasoning_effort: str | None = (
        None  # Reasoning effort level: "xhigh", "high", "medium", "low", "minimal", "none", or None
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
    timeout: int = 180  # Default timeout in seconds
    created_at: Annotated[
        datetime,
        Field(
            description="Timestamp when this data was created",
            default_factory=lambda: datetime.now(UTC),
        ),
    ]
    updated_at: Annotated[
        datetime,
        Field(
            description="Timestamp when this data was updated",
            default_factory=lambda: datetime.now(UTC),
        ),
    ]

    @field_serializer("created_at", "updated_at")
    @classmethod
    def serialize_datetime(cls, v: datetime) -> str:
        return v.isoformat(timespec="milliseconds")

    @staticmethod
    async def get(model_id: str) -> "LLMModelInfo":
        """Get a model by ID with Redis caching.

        The model info is cached in Redis for 3 minutes.

        Args:
            model_id: ID of the model to retrieve

        Returns:
            LLMModelInfo: The model info if found, None otherwise
        """
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
                await redis.set(
                    cache_key,
                    model_info.model_dump_json(),
                    ex=cache_ttl,
                )

                return model_info

        # If not found in database, check AVAILABLE_MODELS.
        # Try exact key first (supports both "provider:id" and legacy "id" keys).
        if model_id in AVAILABLE_MODELS:
            model_info = AVAILABLE_MODELS[model_id]

            # Cache the model in Redis
            await redis.set(cache_key, model_info.model_dump_json(), ex=cache_ttl)

            return model_info

        # Backward-compatible fallback: match by bare model id.
        # If multiple providers have the same model id, prefer native over OpenRouter.
        matching_keys = _MODEL_ID_INDEX.get(model_id, [])
        fallback: LLMModelInfo | None = None
        for key in matching_keys:
            candidate = AVAILABLE_MODELS[key]
            if fallback is None or (
                fallback.provider == LLMProvider.OPENROUTER
                and candidate.provider != LLMProvider.OPENROUTER
            ):
                fallback = candidate
        if fallback is not None:
            logger.debug(
                "Model %s resolved via index to %s:%s",
                model_id,
                fallback.provider.value,
                fallback.id,
            )
            await redis.set(cache_key, fallback.model_dump_json(), ex=cache_ttl)
            return fallback

        # Not found anywhere
        raise IntentKitAPIError(
            400,
            "ModelNotFound",
            f"Model {model_id} not found, maybe deprecated, please change it in the agent configuration.",
        )

    @classmethod
    async def get_all(cls, session: AsyncSession | None = None) -> list["LLMModelInfo"]:
        """Return all models merged from defaults and database overrides."""

        if session is None:
            async with get_session() as db:
                return await cls.get_all(session=db)

        models: dict[str, LLMModelInfo] = {
            model_id: model.model_copy(deep=True)
            for model_id, model in AVAILABLE_MODELS.items()
        }

        result = await session.execute(select(LLMModelInfoTable))
        for row in result.scalars():
            model_info = cls.model_validate(row)
            key = f"{model_info.provider.value}:{model_info.id}"
            models[key] = model_info

        return list(models.values())

    async def calculate_cost(
        self, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0
    ) -> Decimal:
        """Calculate the cost for a given number of tokens."""
        global credit_per_usdc
        if not credit_per_usdc:
            credit_per_usdc = (await AppSetting.payment()).credit_per_usdc

        # Determine effective price for cached input tokens
        effective_cached_price = (
            self.cached_input_price
            if self.cached_input_price is not None
            else self.input_price
        )
        # Clamp cached to total input (defensive against provider inconsistencies)
        effective_cached = min(cached_input_tokens, input_tokens)
        # Non-cached input tokens = total input - cached
        non_cached_input = input_tokens - effective_cached

        input_cost = (
            credit_per_usdc
            * Decimal(non_cached_input)
            * self.input_price
            / Decimal(1000000)
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        cached_input_cost = (
            credit_per_usdc
            * Decimal(effective_cached)
            * effective_cached_price
            / Decimal(1000000)
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        output_cost = (
            credit_per_usdc
            * Decimal(output_tokens)
            * self.output_price
            / Decimal(1000000)
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        return (input_cost + cached_input_cost + output_cost).quantize(
            FOURPLACES, rounding=ROUND_HALF_UP
        )


# Default models loaded from CSV
AVAILABLE_MODELS = load_default_llm_models()

# Reverse index: model id → list of composite keys in AVAILABLE_MODELS.
# Indexed by both full id (e.g. "openai/gpt-5.4-mini") and base name after "/"
# (e.g. "gpt-5.4-mini") for backward compatibility with legacy agent configs.
_MODEL_ID_INDEX: dict[str, list[str]] = {}
for _key, _model in AVAILABLE_MODELS.items():
    _MODEL_ID_INDEX.setdefault(_model.id, []).append(_key)
    if "/" in _model.id:
        _base = _model.id.rsplit("/", 1)[1]
        _MODEL_ID_INDEX.setdefault(_base, []).append(_key)

# USD cost per single web search call, by provider.
# OpenRouter bundles search cost in token billing — no separate charge.
_SEARCH_PRICE_BY_PROVIDER: dict[LLMProvider, Decimal] = {
    LLMProvider.OPENAI: Decimal("0.01"),
    LLMProvider.GOOGLE: Decimal("0.014"),
    LLMProvider.XAI: Decimal("0.005"),
}


def get_search_price(provider: LLMProvider) -> Decimal | None:
    """Return the per-call web search price for a provider, or None if not applicable."""
    return _SEARCH_PRICE_BY_PROVIDER.get(provider)


async def calculate_search_cost(provider: LLMProvider, search_count: int) -> Decimal:
    """Calculate credit cost for web search calls based on provider pricing."""
    price = get_search_price(provider)
    if not price or search_count <= 0:
        return Decimal("0")
    global credit_per_usdc
    if not credit_per_usdc:
        credit_per_usdc = (await AppSetting.payment()).credit_per_usdc
    return (credit_per_usdc * Decimal(search_count) * price).quantize(
        FOURPLACES, rounding=ROUND_HALF_UP
    )


class LLMModel(BaseModel):
    """Base model for LLM configuration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

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
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return the LLM instance based on the configuration."""
        _ = params
        raise NotImplementedError("Subclasses must implement create_instance")

    async def get_token_limit(self) -> int:
        """Get the token limit for this model."""
        info = await self.model_info()
        return info.context_length

    async def calculate_cost(
        self, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0
    ) -> Decimal:
        """Calculate the cost for a given number of tokens."""
        info = await self.model_info()
        return await info.calculate_cost(
            input_tokens, output_tokens, cached_input_tokens
        )


class OpenAILLM(LLMModel):
    """OpenAI LLM configuration."""

    @override
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return a ChatOpenAI instance."""
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model_name": info.id,
            "openai_api_key": config.openai_api_key,
            "timeout": info.timeout,
            "max_retries": 3,
            "use_responses_api": True,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        if info.reasoning_effort and info.reasoning_effort != "none":
            kwargs["reasoning_effort"] = info.reasoning_effort

        # Update kwargs with params to allow overriding
        kwargs.update(params)

        logger.debug("Creating ChatOpenAI instance with kwargs: %s", kwargs)

        return ChatOpenAI(**kwargs)


class DeepseekLLM(LLMModel):
    """Deepseek LLM configuration."""

    @override
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return a ChatDeepseek instance."""

        from langchain_deepseek import ChatDeepSeek

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model": info.id,
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

        # Update kwargs with params to allow overriding
        kwargs.update(params)

        return ChatDeepSeek(**kwargs)


class XAILLM(LLMModel):
    """XAI (Grok) LLM configuration."""

    @override
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return a ChatOpenAI instance configured for xAI."""
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model_name": info.id,
            "openai_api_key": config.xai_api_key,
            "openai_api_base": "https://api.x.ai/v1",
            "timeout": info.timeout,
            "max_retries": 3,
            "use_responses_api": True,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        # Update kwargs with params to allow overriding
        kwargs.update(params)

        from langchain_core.utils.function_calling import convert_to_openai_tool

        class ChatXAIAdapter(ChatOpenAI):
            @override
            def bind_tools(
                self,
                tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
                **kwargs: Any,
            ) -> Runnable[LanguageModelInput, AIMessage]:
                formatted_tools = []
                for tool in tools:
                    if isinstance(tool, dict) and tool.get("type") in {
                        "web_search",
                        "x_search",
                    }:
                        formatted_tools.append(tool)
                    else:
                        formatted_tools.append(
                            convert_to_openai_tool(tool, strict=kwargs.get("strict"))
                        )
                return self.bind(tools=formatted_tools, **kwargs)

            @override
            def _generate(
                self,
                messages: list[BaseMessage],
                stop: list[str] | None = None,
                run_manager: Any | None = None,
                **kwargs: Any,
            ) -> ChatResult:
                """Override generate to filter out xAI tools from the response."""
                result = super()._generate(messages, stop, run_manager, **kwargs)
                for generation in result.generations:
                    message = generation.message
                    if isinstance(message, AIMessage) and message.tool_calls:
                        # filter out xAI tools
                        message.tool_calls = [
                            tool
                            for tool in message.tool_calls
                            if tool["name"]
                            not in {
                                "x_semantic_search",
                                "x_keyword_search",
                                "x_search",
                                "web_search",
                            }
                        ]
                        # if no tools left, reset finish_reason
                        if not message.tool_calls:
                            if (
                                hasattr(generation, "generation_info")
                                and generation.generation_info
                            ):
                                generation.generation_info["finish_reason"] = "stop"
                return result

            @override
            async def _agenerate(
                self,
                messages: list[BaseMessage],
                stop: list[str] | None = None,
                run_manager: Any | None = None,
                **kwargs: Any,
            ) -> ChatResult:
                """Override agenerate to filter out xAI tools from the response."""
                result = await super()._agenerate(messages, stop, run_manager, **kwargs)
                for generation in result.generations:
                    message = generation.message
                    if isinstance(message, AIMessage) and message.tool_calls:
                        # filter out xAI tools
                        message.tool_calls = [
                            tool
                            for tool in message.tool_calls
                            if tool["name"]
                            not in {
                                "x_semantic_search",
                                "x_keyword_search",
                                "x_search",
                                "web_search",
                            }
                        ]
                        # if no tools left, reset finish_reason
                        if not message.tool_calls:
                            if (
                                hasattr(generation, "generation_info")
                                and generation.generation_info
                            ):
                                generation.generation_info["finish_reason"] = "stop"
                return result

        return ChatXAIAdapter(**kwargs)


class OpenRouterLLM(LLMModel):
    """OpenRouter LLM configuration."""

    @override
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return a ChatOpenRouter instance with server tool support."""

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model": info.id,
            "api_key": config.openrouter_api_key,
            "timeout": info.timeout * 1000,
            "max_retries": 3,
            # Attribution headers so OpenRouter dashboard credits IntentKit
            # instead of the LangChain defaults baked into langchain-openrouter.
            "app_url": "https://github.com/crestalnetwork/intentkit",
            "app_title": "IntentKit",
            "app_categories": ["cloud-agent"],
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        if info.reasoning_effort:
            kwargs["reasoning"] = {"effort": info.reasoning_effort}

        # Update kwargs with params to allow overriding
        kwargs.update(params)

        return _create_openrouter_with_server_tools(**kwargs)


_openrouter_usage_cost_fields_injected = False


def _inject_cost_fields_into_chat_usage() -> None:
    """Add ``cost`` / ``cost_details`` to the SDK's ``ChatUsage`` schema.

    OpenRouter's ``/chat/completions`` response includes ``cost`` inside the
    ``usage`` object, but ``openrouter`` SDK's generated ``ChatUsage`` model
    (v0.9.1) does not declare those fields, so Pydantic validation drops them
    and ``langchain-openrouter`` never surfaces them in ``response_metadata``.

    Injecting the fields lets cost round-trip without a fork. Remove this
    helper once the SDK adds the fields natively.
    """
    global _openrouter_usage_cost_fields_injected  # noqa: PLW0603
    if _openrouter_usage_cost_fields_injected:
        return
    try:
        from openrouter.components import ChatUsage  # type: ignore[import-untyped]
        from pydantic.fields import FieldInfo

        if "cost" in ChatUsage.model_fields:
            _openrouter_usage_cost_fields_injected = True
            return
        cost_type: Any = float | None
        cost_details_type: Any = dict[str, Any] | None
        ChatUsage.__annotations__["cost"] = cost_type
        ChatUsage.__annotations__["cost_details"] = cost_details_type
        ChatUsage.model_fields["cost"] = FieldInfo(annotation=cost_type, default=None)
        ChatUsage.model_fields["cost_details"] = FieldInfo(
            annotation=cost_details_type, default=None
        )
        ChatUsage.model_rebuild(force=True)
        _openrouter_usage_cost_fields_injected = True
    except Exception:
        logger.warning(
            "Failed to inject cost fields into OpenRouter ChatUsage", exc_info=True
        )


def _create_openrouter_with_server_tools(**kwargs: Any) -> BaseChatModel:
    """Create a ChatOpenRouter subclass that supports server tools.

    OpenRouter server tools (e.g. ``{"type": "openrouter:web_search"}``) are
    not recognised by ``convert_to_openai_tool`` used inside the upstream
    ``ChatOpenRouter.bind_tools``. This subclass overrides ``bind_tools`` to
    pull server-tool dicts out, delegate the rest to the parent, and re-inject
    the server tools into the bound kwargs so they are sent as-is in the API
    request.

    The underlying ``openrouter`` SDK (>=0.8.0) exposes ``ChatFunctionTool`` as
    a discriminated union that natively accepts the ``openrouter:`` server-tool
    types we use, so no SDK-level patch is required for tool types.
    """
    from langchain_openrouter import ChatOpenRouter

    _inject_cost_fields_into_chat_usage()

    class _WithServerTools(ChatOpenRouter):
        @override
        def bind_tools(
            self,
            tools: Sequence[dict[str, Any] | type | Callable | BaseTool],
            **bt_kwargs: Any,
        ) -> Runnable[LanguageModelInput, AIMessage]:
            server_tools: list[dict[str, Any]] = []
            regular_tools: list[dict[str, Any] | type | Callable | BaseTool] = []
            for tool in tools:
                if (
                    isinstance(tool, dict)
                    and isinstance(tool.get("type"), str)
                    and tool["type"].startswith("openrouter:")
                ):
                    server_tools.append(tool)
                else:
                    regular_tools.append(tool)

            bound = super().bind_tools(regular_tools, **bt_kwargs)

            if server_tools:
                bound_kwargs: dict[str, Any] = bound.kwargs  # pyright: ignore[reportAttributeAccessIssue]
                existing = list(bound_kwargs.get("tools", []))
                updated = {k: v for k, v in bound_kwargs.items() if k != "tools"}
                return self.bind(tools=existing + server_tools, **updated)
            return bound

    return _WithServerTools(**kwargs)


class GoogleLLM(LLMModel):
    """Google LLM configuration."""

    @override
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return a ChatGoogleGenerativeAI instance."""
        from langchain_google_genai import ChatGoogleGenerativeAI

        info = await self.model_info()
        use_vertexai = config.google_genai_use_vertexai is True

        kwargs: dict[str, Any] = {
            "model": info.id,
            "api_key": config.google_api_key,
            "timeout": info.timeout,
            "max_retries": 3,
        }
        if use_vertexai:
            kwargs["vertexai"] = True
            if config.google_cloud_project:
                kwargs["project"] = config.google_cloud_project

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        # Update kwargs with params to allow overriding
        kwargs.update(params)

        return ChatGoogleGenerativeAI(**kwargs)


# Factory function to create the appropriate LLM model based on the model name
class OllamaLLM(LLMModel):
    """Ollama LLM configuration."""

    @override
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return a ChatOllama instance."""
        from langchain_ollama import ChatOllama

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model": info.id,
            "base_url": "http://localhost:11434",
            "temperature": self.temperature,
            # Ollama specific parameters
            "keep_alive": -1,  # Keep the model loaded indefinitely
        }

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        # Update kwargs with params to allow overriding
        kwargs.update(params)

        return ChatOllama(**kwargs)


class MiniMaxLLM(LLMModel):
    """MiniMax LLM configuration using Anthropic-compatible API."""

    @override
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return a ChatAnthropic instance for MiniMax."""
        from langchain_anthropic import ChatAnthropic

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model": info.id,
            "api_key": config.minimax_api_key,
            "base_url": "https://api.minimax.io/anthropic",
            "timeout": info.timeout,
            "max_retries": 3,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        # Update kwargs with params to allow overriding
        kwargs.update(params)

        return ChatAnthropic(**kwargs)


class AnthropicCompatibleLLM(LLMModel):
    """Anthropic Compatible LLM configuration."""

    @override
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return a ChatAnthropic instance for Anthropic-compatible provider."""
        from langchain_anthropic import ChatAnthropic

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model": info.id,
            "api_key": config.anthropic_compatible_api_key,
            "base_url": config.anthropic_compatible_base_url,
            "timeout": info.timeout,
            "max_retries": 3,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        # Update kwargs with params to allow overriding
        kwargs.update(params)

        return ChatAnthropic(**kwargs)


class OpenAICompatibleLLM(LLMModel):
    """OpenAI Compatible LLM configuration."""

    @override
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return a ChatOpenAI instance for OpenAI-compatible provider."""
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model_name": info.id,
            "openai_api_base": config.openai_compatible_base_url,
            "timeout": info.timeout,
            "max_retries": 3,
        }

        kwargs["openai_api_key"] = config.openai_compatible_api_key

        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        if info.reasoning_effort and info.reasoning_effort != "none":
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}

        kwargs.update(params)

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

    provider_map: dict[LLMProvider, type[LLMModel]] = {
        LLMProvider.GOOGLE: GoogleLLM,
        LLMProvider.DEEPSEEK: DeepseekLLM,
        LLMProvider.XAI: XAILLM,
        LLMProvider.OPENROUTER: OpenRouterLLM,
        LLMProvider.OLLAMA: OllamaLLM,
        LLMProvider.OPENAI: OpenAILLM,
        LLMProvider.MINIMAX: MiniMaxLLM,
        LLMProvider.OPENAI_COMPATIBLE: OpenAICompatibleLLM,
        LLMProvider.ANTHROPIC_COMPATIBLE: AnthropicCompatibleLLM,
    }

    model_class = provider_map.get(info.provider, OpenAILLM)

    return model_class(
        model_name=model_name,
        temperature=temperature,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        info=info,
    )
