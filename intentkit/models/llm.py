import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Callable, ClassVar, Literal, get_args

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
from intentkit.utils.yaml import safe_load

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
        rows: list[dict[str, Any]] = safe_load(f) or []

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


# Unified reasoning/thinking effort scale (OpenRouter's enum), ordered weakest
# to strongest. Agent-facing values; providers map or clamp them as needed.
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]

REASONING_EFFORT_SCALE: tuple[str, ...] = get_args(ReasoningEffort)


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
    legacy_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Retired model ids this model supersedes. Agents still storing "
            "one of these ids are routed to this model at resolve time."
        ),
    )
    enabled: bool = Field(default=True)
    input_price: Decimal  # Price per 1M input tokens in USD
    cached_input_price: Decimal | None = None  # Price per 1M cached input tokens in USD
    output_price: Decimal  # Price per 1M output tokens in USD
    price_level: int | None = Field(
        default=None, ge=1, le=5
    )  # Price level rating from 1-5
    context_length: int  # Maximum context length in tokens
    output_length: int  # Maximum output length in tokens
    compress_cold: int | None = Field(
        default=None,
        ge=1,
        description=(
            "History token threshold that triggers compression when the "
            "previous LLM request is more than a day old. None means the "
            "default of 20,000 tokens."
        ),
    )
    compress_warm: int | None = Field(
        default=None,
        ge=1,
        description=(
            "History token threshold that triggers compression when the "
            "previous LLM request is within a day. None means 50% of "
            "context_length."
        ),
    )
    compress_hot: int | None = Field(
        default=None,
        ge=1,
        description=(
            "History token threshold that triggers compression when the "
            "previous LLM request is within an hour. None means 80% of "
            "context_length."
        ),
    )
    intelligence: int = Field(ge=1, le=5)  # Intelligence rating from 1-5
    speed: int = Field(ge=1, le=5)  # Speed rating from 1-5
    supports_image_input: bool = False
    supports_audio_input: bool = False
    supports_video_input: bool = False
    supports_file_input: bool = False
    # Default effort when the agent doesn't set one. "none" means the model
    # runs without reasoning; None means not applicable.
    reasoning_effort: ReasoningEffort | None = None
    # Efforts this model actually supports (per the provider's official docs).
    # Requests are clamped to the nearest member; None passes them through.
    reasoning_levels: list[ReasoningEffort] | None = None
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

    def resolve_reasoning_effort(
        self, requested: ReasoningEffort | None
    ) -> ReasoningEffort | None:
        """Effective effort for a request: the agent's choice clamped to what
        this model supports, falling back to the catalog default when unset.

        A "none" request against a model that cannot disable reasoning clamps
        to the weakest supported level. Other unsupported values go to the
        nearest supported level, preferring non-"none" members (ties round
        up), so a positive request only lands on "none" when the model
        supports nothing else.
        """
        effort = requested or self.reasoning_effort
        if effort is None or not self.reasoning_levels:
            return effort
        if effort in self.reasoning_levels:
            return effort
        candidates: list[ReasoningEffort] = [
            lv for lv in self.reasoning_levels if lv != "none"
        ]
        if effort == "none" or not candidates:
            return min(self.reasoning_levels, key=REASONING_EFFORT_SCALE.index)
        idx = REASONING_EFFORT_SCALE.index(effort)
        return min(
            candidates,
            key=lambda lv: (
                abs(REASONING_EFFORT_SCALE.index(lv) - idx),
                -REASONING_EFFORT_SCALE.index(lv),
            ),
        )

    def compress_thresholds(self) -> tuple[int, int, int]:
        """Effective (cold, warm, hot) history-compression thresholds in tokens.

        Defaults: cold 20,000 tokens, warm 50% of context, hot 80% of context;
        each is overridable per model via ``compress_cold/warm/hot``. The
        values are clamped downward so that cold <= warm <= hot always holds
        (relevant for small-context models where 50% of context is below the
        20k cold default).
        """
        hot = (
            self.compress_hot
            if self.compress_hot is not None
            else int(self.context_length * 0.8)
        )
        warm = min(
            self.compress_warm
            if self.compress_warm is not None
            else int(self.context_length * 0.5),
            hot,
        )
        cold = min(
            self.compress_cold if self.compress_cold is not None else 20_000, warm
        )
        return cold, warm, hot

    @staticmethod
    async def get(model_id: str) -> "LLMModelInfo":
        """Get a model by ID from the in-memory catalog.

        Resolution order:

        1. Exact key — supports both the composite ``provider:id`` key and a
           legacy bare ``id``.
        2. Backward-compatible fallback via the id index (bare ids, base names
           after "/", and ``legacy_ids`` of superseding models); when several
           providers match, native providers are preferred over OpenRouter.

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
            base = fallback.id.rsplit("/", 1)[1] if "/" in fallback.id else fallback.id
            if model_id in (fallback.id, base):
                logger.debug(
                    "Model %s resolved via index to %s:%s",
                    model_id,
                    fallback.provider.value,
                    fallback.id,
                )
            else:
                # Legacy id routed to its successor: pricing/capabilities
                # differ from what the agent originally stored, so keep this
                # visible in logs.
                logger.info(
                    "Legacy model id %s routed to %s:%s",
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

    def cost_usd(
        self, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0
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
        cached_price = (
            self.cached_input_price
            if self.cached_input_price is not None
            else self.input_price
        )
        return (
            Decimal(non_cached) * self.input_price
            + Decimal(cached) * cached_price
            + Decimal(output_tokens) * self.output_price
        ) / Decimal(1000000)


# Default models loaded from the YAML catalog
AVAILABLE_MODELS = load_default_llm_models()


def build_model_id_index(models: dict[str, "LLMModelInfo"]) -> dict[str, list[str]]:
    """Build the reverse index: model id → list of composite keys in ``models``.

    Each model is indexed by its full id (e.g. "openai/gpt-5.6-luna"), the
    base name after "/" (e.g. "gpt-5.6-luna"), and its ``legacy_ids`` (retired
    ids routed to their successor), so agents storing any of those keep
    resolving. A legacy id (or its base name) that collides with anything a
    live model claims is ignored — the live model always wins.
    """
    index: dict[str, list[str]] = {}

    for key, model in models.items():
        index.setdefault(model.id, []).append(key)
        if "/" in model.id:
            index.setdefault(model.id.rsplit("/", 1)[1], []).append(key)

    # Everything live models claim (full ids and base names); legacy routing
    # must never shadow these. Snapshot before adding any legacy entry so the
    # guard does not depend on catalog order.
    live_claims = set(index)

    for key, model in models.items():
        for legacy in model.legacy_ids:
            if legacy in live_claims:
                logger.warning(
                    "legacy id %s on %s collides with a live model id; ignored",
                    legacy,
                    model.id,
                )
                continue
            index.setdefault(legacy, []).append(key)
            if "/" in legacy:
                base = legacy.rsplit("/", 1)[1]
                if base not in live_claims:
                    index.setdefault(base, []).append(key)
    return index


_MODEL_ID_INDEX: dict[str, list[str]] = build_model_id_index(AVAILABLE_MODELS)


def is_model_resolvable(model_id: str) -> bool:
    """Whether ``LLMModelInfo.get`` would resolve this id in this deployment.

    Covers composite keys, bare ids, base names after "/", and legacy ids.
    """
    return model_id in AVAILABLE_MODELS or model_id in _MODEL_ID_INDEX


# USD cost per single provider-billed server-side web search call. Only
# providers whose native search tool we use appear here. OpenRouter, deepseek,
# minimax, etc. run our client-side web_search tool instead, whose cost is
# accounted by that tool, so they have no entry.
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
    # Agent-requested reasoning effort (unified scale); None follows the
    # model's catalog default. Resolved per request via
    # ``info.resolve_reasoning_effort``.
    reasoning_effort: ReasoningEffort | None = None
    info: LLMModelInfo

    async def model_info(self) -> LLMModelInfo:
        """Resolve this model's info from the in-memory catalog.

        Raises IntentKitAPIError if the model is not found.
        """
        model_info = await LLMModelInfo.get(self.model_name)
        return model_info

    # This will be implemented by subclasses to return the appropriate LLM instance
    async def create_instance(
        self, params: dict[str, Any] | None = None
    ) -> BaseChatModel:
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
    async def create_instance(
        self, params: dict[str, Any] | None = None
    ) -> BaseChatModel:
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

        # GPT-5.6 accepts the full scale including an explicit "none".
        effort = info.resolve_reasoning_effort(self.reasoning_effort)
        if effort is not None:
            kwargs["reasoning_effort"] = effort

        # Update kwargs with params to allow overriding
        kwargs.update(params or {})

        logger.debug("Creating ChatOpenAI instance with kwargs: %s", kwargs)

        return ChatOpenAI(**kwargs)


class DeepseekLLM(LLMModel):
    """Deepseek LLM configuration."""

    @override
    async def create_instance(
        self, params: dict[str, Any] | None = None
    ) -> BaseChatModel:
        """Create and return a ChatDeepseek instance."""

        from langchain_deepseek import ChatDeepSeek

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model": info.id,
            "api_key": config.deepseek_api_key,
            "timeout": info.timeout,
            "max_retries": 3,
        }

        # DeepSeek V4 defaults to thinking mode server-side; pass the toggle
        # explicitly so non-reasoning requests actually run without it.
        effort = info.resolve_reasoning_effort(self.reasoning_effort)
        if effort and effort != "none":
            kwargs["extra_body"] = {
                "thinking": {"type": "enabled"},
                # DeepSeek accepts high|max; the clamp keeps values in range.
                "reasoning_effort": effort,
            }
        else:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        # Update kwargs with params to allow overriding
        kwargs.update(params or {})

        return ChatDeepSeek(**kwargs)


class XAILLM(LLMModel):
    """XAI (Grok) LLM configuration."""

    @override
    async def create_instance(
        self, params: dict[str, Any] | None = None
    ) -> BaseChatModel:
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

        # Grok reasoning cannot be disabled and rejects "none"; the clamp
        # (levels low/medium/high) guarantees a value xAI accepts.
        effort = info.resolve_reasoning_effort(self.reasoning_effort)
        if effort and effort != "none":
            kwargs["reasoning_effort"] = effort

        # Update kwargs with params to allow overriding
        kwargs.update(params or {})

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
    async def create_instance(
        self, params: dict[str, Any] | None = None
    ) -> BaseChatModel:
        """Create and return a ChatOpenRouter instance."""
        from langchain_openrouter import ChatOpenRouter

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

        # Agent efforts use OpenRouter's own enum, so the clamped value goes on
        # the wire as-is. "none" is deliberately forwarded: OpenRouter uses it
        # to disable reasoning on hybrid upstream models.
        effort = info.resolve_reasoning_effort(self.reasoning_effort)
        if effort is not None:
            kwargs["reasoning"] = {"effort": effort}

        # Pin the upstream provider on OpenRouter when configured; otherwise leave
        # routing to OpenRouter. allow_fallbacks=False makes it a hard lock so the
        # request fails rather than silently routing to a different provider.
        if info.origin_provider:
            kwargs["openrouter_provider"] = {
                "order": [info.origin_provider],
                "allow_fallbacks": False,
            }

        # Update kwargs with params to allow overriding
        kwargs.update(params or {})

        return ChatOpenRouter(**kwargs)


class GoogleLLM(LLMModel):
    """Google LLM configuration."""

    @override
    async def create_instance(
        self, params: dict[str, Any] | None = None
    ) -> BaseChatModel:
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

        # Gemini takes thinking_level minimal..high; the clamp (catalog
        # reasoning_levels) keeps values inside each model's supported range.
        effort = info.resolve_reasoning_effort(self.reasoning_effort)
        if effort and effort != "none":
            kwargs["thinking_level"] = effort

        # Update kwargs with params to allow overriding
        kwargs.update(params or {})

        return ChatGoogleGenerativeAI(**kwargs)


class OllamaLLM(LLMModel):
    """Ollama LLM configuration."""

    @override
    async def create_instance(
        self, params: dict[str, Any] | None = None
    ) -> BaseChatModel:
        """Create and return a ChatOllama instance."""
        from langchain_ollama import ChatOllama

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model": info.id,
            "base_url": "http://localhost:11434",
            # Ollama specific parameters
            "keep_alive": -1,  # Keep the model loaded indefinitely
        }

        # Update kwargs with params to allow overriding
        kwargs.update(params or {})

        return ChatOllama(**kwargs)


class MiniMaxLLM(LLMModel):
    """MiniMax LLM configuration using Anthropic-compatible API."""

    @override
    async def create_instance(
        self, params: dict[str, Any] | None = None
    ) -> BaseChatModel:
        """Create and return a ChatAnthropic instance for MiniMax."""
        from langchain_anthropic import ChatAnthropic

        info = await self.model_info()

        kwargs: dict[str, Any] = {
            "model": info.id,
            "api_key": config.minimax_plan_api_key,
            "base_url": "https://api.minimax.io/anthropic",
            "timeout": info.timeout,
            "max_retries": 3,
        }

        # MiniMax's Anthropic-compatible endpoint defaults to thinking
        # DISABLED (unlike its OpenAI-compatible one), so always send the
        # toggle. It only understands "adaptive" and "disabled". Note the
        # generic AnthropicCompatibleLLM below deliberately sends no thinking
        # config: arbitrary endpoints disagree on the accepted shape.
        effort = info.resolve_reasoning_effort(self.reasoning_effort)
        kwargs["thinking"] = {
            "type": "adaptive" if effort and effort != "none" else "disabled"
        }

        # Update kwargs with params to allow overriding
        kwargs.update(params or {})

        return ChatAnthropic(**kwargs)


class MimoPlanLLM(LLMModel):
    """Xiaomi MiMo Token Plan LLM configuration (OpenAI-compatible API)."""

    @override
    async def create_instance(
        self, params: dict[str, Any] | None = None
    ) -> BaseChatModel:
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

        # MiMo V2.5 defaults to thinking mode server-side; pass the toggle
        # explicitly so "none" requests actually run without it.
        effort = info.resolve_reasoning_effort(self.reasoning_effort)
        kwargs["extra_body"] = {
            "thinking": {
                "type": "enabled" if effort and effort != "none" else "disabled"
            }
        }

        kwargs.update(params or {})

        return ChatOpenAI(**kwargs)


class AnthropicCompatibleLLM(LLMModel):
    """Anthropic Compatible LLM configuration."""

    @override
    async def create_instance(
        self, params: dict[str, Any] | None = None
    ) -> BaseChatModel:
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

        # Update kwargs with params to allow overriding
        kwargs.update(params or {})

        return ChatAnthropic(**kwargs)


class OpenAICompatibleLLM(LLMModel):
    """OpenAI Compatible LLM configuration."""

    @override
    async def create_instance(
        self, params: dict[str, Any] | None = None
    ) -> BaseChatModel:
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

        effort = info.resolve_reasoning_effort(self.reasoning_effort)
        if effort and effort != "none":
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}

        kwargs.update(params or {})

        return ChatOpenAI(**kwargs)


# Factory function to create the appropriate LLM model based on the model name
async def create_llm_model(
    model_name: str,
    reasoning_effort: ReasoningEffort | None = None,
) -> LLMModel:
    """
    Create an LLM model instance based on the model name.

    Args:
        model_name: The name of the model to use
        reasoning_effort: Requested reasoning effort (unified scale); None
            follows the model's catalog default

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
        reasoning_effort=reasoning_effort,
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
