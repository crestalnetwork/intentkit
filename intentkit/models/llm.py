import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Callable, ClassVar

import yaml
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from typing_extensions import override

from intentkit.config.config import config
from intentkit.models.app_setting import AppSetting
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

# Process-lifetime cache for the credit-per-USDC rate fetched from AppSetting.
# This value is loaded on first use and never refreshed until the process restarts,
# which is acceptable because rate changes are infrequent and a restart picks them up.
credit_per_usdc = None
FOURPLACES = Decimal("0.0001")


def load_default_llm_models() -> dict[str, "LLMModelInfo"]:
    """Load default LLM models from the bundled ``llm.yaml`` catalog.

    Models are keyed by ``{provider}:{id}`` so that the same model ID from
    different providers (e.g. ``deepseek-v4-flash`` via DeepSeek *and* OpenRouter)
    is preserved as separate entries.
    """

    path = Path(__file__).with_name("llm.yaml")
    if not path.exists():
        logger.warning("Default LLM YAML not found at %s", path)
        return {}

    with path.open(encoding="utf-8") as f:
        rows: list[dict[str, Any]] = yaml.safe_load(f) or []

    defaults: dict[str, LLMModelInfo] = {}
    for row in rows:
        row_id = row.get("id") if isinstance(row, dict) else None
        try:
            # Pydantic coerces the catalog's string prices to exact Decimals and
            # validates types; unknown providers raise here and are skipped.
            model = LLMModelInfo.model_validate(row)
            if not model.enabled:
                continue
            if not model.provider.is_configured:
                continue
        except Exception as exc:
            logger.error("Failed to load default LLM model %s: %s", row_id, exc)
            continue
        # Key by provider:id so the same model from different providers is kept
        defaults[f"{model.provider.value}:{model.id}"] = model

    # Load OpenAI Compatible models from config (not the YAML catalog)
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

    # Load Anthropic Compatible models from config (not the YAML catalog)
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
    MIMO_PLAN = "mimo_plan"
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
            self.MINIMAX: bool(config.minimax_plan_api_key),
            self.MIMO_PLAN: bool(config.mimo_plan_api_key),
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
            self.MIMO_PLAN: "MiMo",
            self.OLLAMA: "Ollama",
            self.OPENAI_COMPATIBLE: config.openai_compatible_provider,
            self.ANTHROPIC_COMPATIBLE: config.anthropic_compatible_provider,
        }
        return display_names.get(self, self.value)


class LLMPricingTier(BaseModel):
    """Token pricing for one service tier and input-length range."""

    service_tier: str = "standard"
    input_tokens_lte: int | None = Field(default=None, ge=0)
    input_tokens_gt: int | None = Field(default=None, ge=0)
    input_price: Decimal
    cached_input_price: Decimal | None = None
    cache_write_price: Decimal | None = None
    output_price: Decimal

    def matches(self, input_tokens: int, service_tier: str) -> bool:
        """Return whether this tier applies to the request."""
        if self.service_tier != service_tier:
            return False
        if self.input_tokens_lte is not None and input_tokens > self.input_tokens_lte:
            return False
        return self.input_tokens_gt is None or input_tokens > self.input_tokens_gt


class LLMModelInfo(BaseModel):
    """Information about an LLM model."""

    id: str
    name: str
    provider: LLMProvider
    origin_provider: str | None = Field(
        default=None,
        description=(
            "OpenRouter-only: pin the upstream provider using an OpenRouter "
            "provider routing slug. None lets OpenRouter choose."
        ),
    )
    enabled: bool = Field(default=True)
    input_price: Decimal  # Price per 1M input tokens in USD
    cached_input_price: Decimal | None = None  # Price per 1M cached input tokens in USD
    cache_write_price: Decimal | None = None  # Price per 1M cache-write tokens in USD
    output_price: Decimal  # Price per 1M output tokens in USD
    pricing_tiers: list[LLMPricingTier] = Field(default_factory=list)
    price_level: int | None = Field(
        default=None, ge=1, le=5
    )  # Price level rating from 1-5
    context_length: int  # Maximum context length in tokens
    output_length: int  # Maximum output length in tokens
    intelligence: int = Field(ge=1, le=5)  # Intelligence rating from 1-5
    speed: int = Field(ge=1, le=5)  # Speed rating from 1-5
    supports_image_input: bool = False
    supports_audio_input: bool = False
    supports_video_input: bool = False
    supports_file_input: bool = False
    reasoning_effort: str | None = (
        None  # Reasoning effort level: "xhigh", "high", "medium", "low", "minimal", "none", or None
    )
    thinking_modes: list[str] = Field(default_factory=list)
    default_thinking_mode: str | None = None
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
        """Get a model by ID from the in-memory catalog.

        Resolution order:

        1. Exact key — supports both the composite ``provider:id`` key and a
           legacy bare ``id``.
        2. Backward-compatible fallback by bare model id; when several providers
           expose the same id, native providers are preferred over OpenRouter.

        Args:
            model_id: ID of the model to retrieve.

        Raises:
            IntentKitAPIError: if no model matches ``model_id``.
        """
        # Try exact key first (supports both "provider:id" and legacy "id" keys).
        if model_id in AVAILABLE_MODELS:
            return AVAILABLE_MODELS[model_id]

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
            return fallback

        # Not found anywhere
        raise IntentKitAPIError(
            400,
            "ModelNotFound",
            f"Model {model_id} not found, maybe deprecated, please change it in the agent configuration.",
        )

    @classmethod
    async def get_all(cls) -> list["LLMModelInfo"]:
        """Return all models from the in-memory catalog.

        Kept ``async`` (despite no I/O) so the awaited call sites stay stable.
        """
        return list(AVAILABLE_MODELS.values())

    def prices_for(
        self, input_tokens: int, service_tier: str = "standard"
    ) -> tuple[Decimal, Decimal | None, Decimal | None, Decimal]:
        """Return prices for the matching service tier and input range."""
        for tier in self.pricing_tiers:
            if tier.matches(input_tokens, service_tier):
                return (
                    tier.input_price,
                    tier.cached_input_price,
                    tier.cache_write_price,
                    tier.output_price,
                )
        return (
            self.input_price,
            self.cached_input_price,
            self.cache_write_price,
            self.output_price,
        )

    async def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
        service_tier: str = "standard",
    ) -> Decimal:
        """Calculate the cost for a given number of tokens."""
        global credit_per_usdc
        if not credit_per_usdc:
            credit_per_usdc = (await AppSetting.payment()).credit_per_usdc

        input_price, cached_input_price, _, output_price = self.prices_for(
            input_tokens, service_tier
        )
        # Determine effective price for cached input tokens
        effective_cached_price = (
            cached_input_price if cached_input_price is not None else input_price
        )
        # Clamp cached to total input (defensive against provider inconsistencies)
        effective_cached = min(cached_input_tokens, input_tokens)
        # Non-cached input tokens = total input - cached
        non_cached_input = input_tokens - effective_cached

        input_cost = (
            credit_per_usdc * Decimal(non_cached_input) * input_price / Decimal(1000000)
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        cached_input_cost = (
            credit_per_usdc
            * Decimal(effective_cached)
            * effective_cached_price
            / Decimal(1000000)
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        output_cost = (
            credit_per_usdc * Decimal(output_tokens) * output_price / Decimal(1000000)
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        return (input_cost + cached_input_cost + output_cost).quantize(
            FOURPLACES, rounding=ROUND_HALF_UP
        )

    def cost_usd(
        self,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
        service_tier: str = "standard",
    ) -> Decimal:
        """USD cost for a generation's token usage.

        Unlike ``calculate_cost`` (which returns a credit amount for billing),
        this is plain USD for observability — sent to Langfuse so its trace cost
        matches our catalog prices, including the discounted cached-input rate.
        """
        input_tokens = max(input_tokens, 0)
        output_tokens = max(output_tokens, 0)
        cached = min(max(cached_input_tokens, 0), input_tokens)
        non_cached = input_tokens - cached
        input_price, cached_input_price, _, output_price = self.prices_for(
            input_tokens, service_tier
        )
        cached_price = (
            cached_input_price if cached_input_price is not None else input_price
        )
        return (
            Decimal(non_cached) * input_price
            + Decimal(cached) * cached_price
            + Decimal(output_tokens) * output_price
        ) / Decimal(1000000)


# Default models loaded from the YAML catalog
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
        """Resolve this model's info from the in-memory catalog.

        Raises IntentKitAPIError if the model is not found.
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
        self,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
        service_tier: str = "standard",
    ) -> Decimal:
        """Calculate the cost for a given number of tokens."""
        info = await self.model_info()
        return await info.calculate_cost(
            input_tokens, output_tokens, cached_input_tokens, service_tier
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

        # Pin the upstream provider on OpenRouter when configured; otherwise leave
        # routing to OpenRouter. allow_fallbacks=False makes it a hard lock so the
        # request fails rather than silently routing to a different provider.
        if info.origin_provider:
            kwargs["openrouter_provider"] = {
                "order": [info.origin_provider],
                "allow_fallbacks": False,
            }

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
            "api_key": config.minimax_plan_api_key,
            "base_url": config.minimax_plan_base_url,
            "timeout": info.timeout,
            "max_retries": 3,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        # Update kwargs with params to allow overriding
        kwargs.update(params)

        return ChatAnthropic(**kwargs)


class MimoPlanLLM(LLMModel):
    """Xiaomi MiMo Token Plan LLM configuration (OpenAI-compatible API)."""

    @override
    async def create_instance(self, params: dict[str, Any] = {}) -> BaseChatModel:
        """Create and return a ChatOpenAI instance configured for MiMo."""
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model_name": info.id,
            "openai_api_key": config.mimo_plan_api_key,
            "openai_api_base": "https://api.xiaomimimo.com/v1",
            "timeout": info.timeout,
            "max_retries": 3,
        }

        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        kwargs.update(params)

        return ChatOpenAI(**kwargs)


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
        LLMProvider.MIMO_PLAN: MimoPlanLLM,
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


def _resolve_generation_cost(response: object) -> float | None:
    """USD cost for a finished LLM run, for Langfuse's per-generation cost.

    Prefers the provider-reported charge (OpenRouter returns the real cost in
    ``response_metadata['cost']``); otherwise prices the run's token usage with
    the catalog's USD rates, so trace cost matches billing and Gemini cache-read
    is counted at the cached rate. Returns ``None`` when neither is available, in
    which case Langfuse falls back to inferring cost from its own model prices.
    """
    try:
        generations = getattr(response, "generations", None)
        if not generations or not generations[-1]:
            return None
        message = getattr(generations[-1][-1], "message", None)
        if message is None:
            return None
        metadata = getattr(message, "response_metadata", None) or {}

        # 1. Provider-reported cost wins (OpenRouter's real charge).
        provider_cost = metadata.get("cost")
        if isinstance(provider_cost, (int, float)) and provider_cost > 0:
            return float(provider_cost)

        # 2. Otherwise price our token usage with catalog rates.
        usage = getattr(message, "usage_metadata", None)
        if not usage:
            return None
        model_name = metadata.get("model_name") or metadata.get("model")
        if isinstance(model_name, str) and model_name.startswith("models/"):
            model_name = model_name[len("models/") :]
        keys = _MODEL_ID_INDEX.get(model_name) if model_name else None
        info = AVAILABLE_MODELS.get(keys[0]) if keys else None
        if info is None:
            return None
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        cached = int((usage.get("input_token_details") or {}).get("cache_read") or 0)
        return float(info.cost_usd(input_tokens, output_tokens, cached))
    except Exception:
        return None


# Register the resolver so the Langfuse callback (config layer) can price
# generations without importing the model catalog. Best-effort: tracing is
# optional and may be unavailable in trimmed environments.
try:
    from intentkit.config.tracing import set_generation_cost_resolver

    set_generation_cost_resolver(_resolve_generation_cost)
except Exception:  # pragma: no cover - tracing is optional
    pass
