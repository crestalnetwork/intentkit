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
_credit_per_usdc = None
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


def _candidate_score(model: "LLMModelInfo") -> int:
    """Score model candidates for the same logical model ID."""
    if not model.provider.is_configured:
        return 0
    if model.provider == LLMProvider.OPENROUTER:
        return 1
    return 2


def _select_preferred_model(
    candidates: list["LLMModelInfo"],
) -> "LLMModelInfo | None":
    """Pick one configured candidate, preferring native providers over OpenRouter."""
    best_model: LLMModelInfo | None = None
    best_score = -1
    for candidate in candidates:
        score = _candidate_score(candidate)
        if score > best_score:
            best_model = candidate
            best_score = score
    return best_model if best_score > 0 else None


def _load_default_llm_models() -> dict[str, "LLMModelInfo"]:
    """Load default LLM models from a CSV file."""

    path = Path(__file__).with_name("llm.csv")
    if not path.exists():
        logger.warning("Default LLM CSV not found at %s", path)
        return {}

    defaults: dict[str, LLMModelInfo] = {}
    model_candidates: dict[str, list[LLMModelInfo]] = {}
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
                    "provider_model_id": row.get("provider_model_id", "").strip()
                    or None,
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
                    "supports_skill_calls": _parse_bool(
                        row.get("supports_skill_calls")
                    ),
                    "supports_structured_output": _parse_bool(
                        row.get("supports_structured_output")
                    ),
                    "reasoning_effort": row.get("reasoning_effort", "").strip() or None,
                    "supports_search": _parse_bool(row.get("supports_search")),
                    "supports_temperature": _parse_bool(
                        row.get("supports_temperature")
                    ),
                    "supports_frequency_penalty": _parse_bool(
                        row.get("supports_frequency_penalty")
                    ),
                    "supports_presence_penalty": _parse_bool(
                        row.get("supports_presence_penalty")
                    ),
                    "api_base": row.get("api_base", "").strip() or None,
                    "timeout": int(row.get("timeout") or 180),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
                model = LLMModelInfo(**attrs)
                if not model.enabled:
                    continue
            except Exception as exc:
                logger.error(
                    "Failed to load default LLM model %s: %s", row.get("id"), exc
                )
                continue
            model_candidates.setdefault(model.id, []).append(model)

    for model_id, candidates in model_candidates.items():
        selected = _select_preferred_model(candidates)
        if selected:
            defaults[model_id] = selected

    return defaults


class LLMProvider(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"
    XAI = "xai"
    OPENROUTER = "openrouter"
    ETERNAL = "eternal"
    REIGENT = "reigent"
    VENICE = "venice"
    OLLAMA = "ollama"

    @property
    def is_configured(self) -> bool:
        """Check if the provider is configured with an API key."""
        config_map = {
            self.OPENAI: bool(config.openai_api_key),
            self.GOOGLE: bool(config.google_api_key),
            self.DEEPSEEK: bool(config.deepseek_api_key),
            self.XAI: bool(config.xai_api_key),
            self.OPENROUTER: bool(config.openrouter_api_key),
            self.ETERNAL: bool(config.eternal_api_key),
            self.REIGENT: bool(config.reigent_api_key),
            self.VENICE: bool(config.venice_api_key),
            self.OLLAMA: True,  # Ollama usually doesn't need a key
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
            self.ETERNAL: "Eternal",
            self.REIGENT: "Reigent",
            self.VENICE: "Venice",
            self.OLLAMA: "Ollama",
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
    supports_skill_calls: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    supports_structured_output: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    reasoning_effort: Mapped[str | None] = mapped_column(String, nullable=True)
    supports_search: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    supports_temperature: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    supports_frequency_penalty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    supports_presence_penalty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    api_base: Mapped[str | None] = mapped_column(String, nullable=True)
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
    provider_model_id: str | None = None
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
    supports_skill_calls: bool = False  # Whether the model supports skill/tool calls
    supports_structured_output: bool = (
        False  # Whether the model supports structured output
    )
    reasoning_effort: str | None = (
        None  # Reasoning effort level: "xhigh", "high", "medium", "low", "minimal", "none", or None
    )
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
    api_base: str | None = None  # Custom API base URL if not using provider's default
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

        # If not found in database, check AVAILABLE_MODELS
        if model_id in AVAILABLE_MODELS:
            model_info = AVAILABLE_MODELS[model_id]

            # Cache the model in Redis
            await redis.set(cache_key, model_info.model_dump_json(), ex=cache_ttl)

            return model_info

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
            models[model_info.id] = model_info

        return list(models.values())

    async def calculate_cost(
        self, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0
    ) -> Decimal:
        """Calculate the cost for a given number of tokens."""
        global _credit_per_usdc
        if not _credit_per_usdc:
            _credit_per_usdc = (await AppSetting.payment()).credit_per_usdc

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
            _credit_per_usdc
            * Decimal(non_cached_input)
            * self.input_price
            / Decimal(1000000)
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        cached_input_cost = (
            _credit_per_usdc
            * Decimal(effective_cached)
            * effective_cached_price
            / Decimal(1000000)
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        output_cost = (
            _credit_per_usdc
            * Decimal(output_tokens)
            * self.output_price
            / Decimal(1000000)
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        return (input_cost + cached_input_cost + output_cost).quantize(
            FOURPLACES, rounding=ROUND_HALF_UP
        )


# Default models loaded from CSV
AVAILABLE_MODELS = _load_default_llm_models()

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
    global _credit_per_usdc
    if not _credit_per_usdc:
        _credit_per_usdc = (await AppSetting.payment()).credit_per_usdc
    return (_credit_per_usdc * Decimal(search_count) * price).quantize(
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
    async def create_instance(self, params: dict[str, Any] = None) -> BaseChatModel:
        """Create and return the LLM instance based on the configuration."""
        if params is None:
            params = {}
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
    async def create_instance(self, params: dict[str, Any] = None) -> BaseChatModel:
        """Create and return a ChatOpenAI instance."""
        if params is None:
            params = {}
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model_name": self.model_name,
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

        if info.api_base:
            kwargs["openai_api_base"] = info.api_base

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
            "model_name": self.model_name,
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
        """Create and return a ChatOpenRouter instance."""
        from langchain_openrouter import ChatOpenRouter

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model": info.provider_model_id or self.model_name,
            "api_key": config.openrouter_api_key,
            "timeout": info.timeout * 1000,
            "max_retries": 3,
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

        return ChatOpenRouter(**kwargs)


class GoogleLLM(LLMModel):
    """Google LLM configuration."""

    @override
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return a ChatGoogleGenerativeAI instance."""
        from langchain_google_genai import ChatGoogleGenerativeAI

        info = await self.model_info()
        use_vertexai = config.google_genai_use_vertexai is True

        kwargs: dict[str, Any] = {
            "model": self.model_name,
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
            "model": self.model_name,
            "base_url": info.api_base or "http://localhost:11434",
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
    }

    model_class = provider_map.get(info.provider, OpenAILLM)

    return model_class(
        model_name=model_name,
        temperature=temperature,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        info=info,
    )
