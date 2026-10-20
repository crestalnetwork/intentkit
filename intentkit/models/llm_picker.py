"""
Logic for selecting the best available LLM model for various tasks.

Each ``pick_*`` function defines a provider-spanning preference list and returns
the first model whose provider is configured in this deployment. The lists are
hand-ranked and meant to be tuned over time — the model catalogue itself lives
in ``llm.yaml``.
"""

from intentkit.config.config import config
from intentkit.models.llm import AVAILABLE_MODELS, LLMProvider

# Universal last-resort model id. Also backstops pick_default_model (the
# TemplateTable column default), so it must be a plausible model even when
# nothing is configured.
_DEFAULT_FALLBACK_MODEL = "gpt-luna"


def _first_configured(
    order: list[tuple[str, LLMProvider]],
    *,
    lite_compatible: bool = False,
    fallback: str | None = None,
) -> str:
    """Return the first model id whose provider is configured.

    The configured OpenAI-/Anthropic-compatible models are appended as a last
    resort (the ``*_lite`` variant when ``lite_compatible`` is set). If no
    provider in the resulting list is configured, ``fallback`` is returned when
    given, otherwise a ``RuntimeError`` is raised.
    """
    candidates = list(order)

    # Append the configured OpenAI-/Anthropic-compatible models as a last
    # resort (the *_lite variant when requested).
    compatible = [
        (
            LLMProvider.OPENAI_COMPATIBLE,
            config.openai_compatible_model_lite
            if lite_compatible
            else config.openai_compatible_model,
        ),
        (
            LLMProvider.ANTHROPIC_COMPATIBLE,
            config.anthropic_compatible_model_lite
            if lite_compatible
            else config.anthropic_compatible_model,
        ),
    ]
    for provider, model_id in compatible:
        if provider.is_configured and model_id:
            candidates.append((model_id, provider))

    for model_id, provider in candidates:
        if provider.is_configured:
            return model_id

    if fallback is not None:
        return fallback
    raise RuntimeError("No model available: missing all required API keys")


def pick_summarize_model() -> str:
    """Pick the best available summarize model based on configured API keys."""
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-flash-lite", LLMProvider.GOOGLE),
        ("deepseek/deepseek-flash", LLMProvider.OPENROUTER),
        ("gpt-luna", LLMProvider.OPENAI),
        ("grok", LLMProvider.XAI),
        ("deepseek-flash", LLMProvider.DEEPSEEK),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("mimo", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, lite_compatible=True)


def pick_default_model() -> str:
    """Pick the best available default model for agents.

    Used as the ``default_factory`` for the agent model field, so it must never
    crash — it falls back to a reasonable model when nothing is configured.
    """
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-flash", LLMProvider.GOOGLE),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("minimax/minimax-flash:free", LLMProvider.OPENROUTER),
        ("gpt-luna", LLMProvider.OPENAI),
        ("grok", LLMProvider.XAI),
        ("deepseek-flash", LLMProvider.DEEPSEEK),
        ("mimo", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_lead_model() -> str:
    """Pick the model for the team lead orchestrator.

    The lead drives user conversation and multi-agent delegation. DeepSeek's
    V4.1 Flash tops agent/tool-driving benchmarks at flash cost (DeepSeek
    states it surpasses V4 Pro), so it heads the list on both its providers.
    """
    order: list[tuple[str, LLMProvider]] = [
        ("deepseek-flash", LLMProvider.DEEPSEEK),
        ("deepseek/deepseek-flash", LLMProvider.OPENROUTER),
        ("gemini-flash", LLMProvider.GOOGLE),
        ("gpt-luna", LLMProvider.OPENAI),
        ("grok", LLMProvider.XAI),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("mimo", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_lite_model() -> str:
    """Pick the cheapest/fastest "lite" model — good enough for simple tasks."""
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-flash-lite", LLMProvider.GOOGLE),
        ("z-ai/glm-flash", LLMProvider.OPENROUTER),
        ("deepseek-flash", LLMProvider.DEEPSEEK),
        # Luna is OpenAI's cheapest tier; glm/deepseek above are still cheaper.
        ("gpt-luna", LLMProvider.OPENAI),
        ("grok", LLMProvider.XAI),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("mimo", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(
        order, lite_compatible=True, fallback=_DEFAULT_FALLBACK_MODEL
    )


def pick_smartest_model() -> str:
    """Pick the highest-intelligence model for complex reasoning."""
    order: list[tuple[str, LLMProvider]] = [
        ("anthropic/claude-opus", LLMProvider.OPENROUTER),
        ("gemini-pro", LLMProvider.GOOGLE),
        ("gpt-sol", LLMProvider.OPENAI),
        ("grok", LLMProvider.XAI),
        ("deepseek-pro", LLMProvider.DEEPSEEK),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("mimo-pro", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_fastest_model() -> str:
    """Pick the lowest-latency model for snappy, simple interactions."""
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-flash-lite", LLMProvider.GOOGLE),
        ("qwen/qwen-flash", LLMProvider.OPENROUTER),
        ("gpt-luna", LLMProvider.OPENAI),
        ("grok", LLMProvider.XAI),
        ("deepseek-flash", LLMProvider.DEEPSEEK),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("mimo", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(
        order, lite_compatible=True, fallback=_DEFAULT_FALLBACK_MODEL
    )


def pick_multimodal_model() -> str:
    """Pick the best model that accepts image/audio/video input."""
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-flash", LLMProvider.GOOGLE),
        ("google/gemini-flash", LLMProvider.OPENROUTER),
        ("mimo", LLMProvider.MIMO_PLAN),
        ("minimax", LLMProvider.MINIMAX),
        ("gpt-terra", LLMProvider.OPENAI),
        ("grok", LLMProvider.XAI),
        ("deepseek-flash", LLMProvider.DEEPSEEK),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_writing_model() -> str:
    """Pick the best model for high-quality general (English) writing."""
    order: list[tuple[str, LLMProvider]] = [
        ("anthropic/claude-sonnet", LLMProvider.OPENROUTER),
        ("gemini-pro", LLMProvider.GOOGLE),
        ("gpt-sol", LLMProvider.OPENAI),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("deepseek-pro", LLMProvider.DEEPSEEK),
        ("grok", LLMProvider.XAI),
        ("mimo-pro", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_chinese_writing_model() -> str:
    """Pick the best model for Chinese writing (Chinese-native models first)."""
    order: list[tuple[str, LLMProvider]] = [
        ("qwen/qwen-max", LLMProvider.OPENROUTER),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("mimo-pro", LLMProvider.MIMO_PLAN),
        ("deepseek-pro", LLMProvider.DEEPSEEK),
        ("gemini-pro", LLMProvider.GOOGLE),
        ("gpt-sol", LLMProvider.OPENAI),
        ("grok", LLMProvider.XAI),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_finance_model() -> str:
    """Pick the best model for financial/quantitative analysis."""
    order: list[tuple[str, LLMProvider]] = [
        ("anthropic/claude-opus", LLMProvider.OPENROUTER),
        ("deepseek-pro", LLMProvider.DEEPSEEK),
        ("gemini-pro", LLMProvider.GOOGLE),
        ("gpt-sol", LLMProvider.OPENAI),
        ("grok", LLMProvider.XAI),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("mimo-pro", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_search_model() -> str:
    """Pick the best model for web/realtime search (native-search providers first)."""
    order: list[tuple[str, LLMProvider]] = [
        ("grok", LLMProvider.XAI),
        ("gemini-flash", LLMProvider.GOOGLE),
        ("gpt-terra", LLMProvider.OPENAI),
        ("x-ai/grok", LLMProvider.OPENROUTER),
        ("deepseek-flash", LLMProvider.DEEPSEEK),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("mimo", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_broadest_knowledge_model() -> str:
    """Pick the model with the broadest world knowledge."""
    order: list[tuple[str, LLMProvider]] = [
        ("anthropic/claude-opus", LLMProvider.OPENROUTER),
        ("gemini-pro", LLMProvider.GOOGLE),
        ("gpt-sol", LLMProvider.OPENAI),
        ("grok", LLMProvider.XAI),
        ("deepseek-pro", LLMProvider.DEEPSEEK),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("mimo-pro", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_long_context_model() -> str:
    """
    Pick the cheapest available model with context length >= 1,000,000 tokens.
    Falls back to any available model if no long-context model is configured.
    """
    # Priority order based on cost (cheapest first), one per provider:
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-flash-lite", LLMProvider.GOOGLE),
        ("deepseek/deepseek-flash", LLMProvider.OPENROUTER),
        ("deepseek-flash", LLMProvider.DEEPSEEK),
        ("gpt-luna", LLMProvider.OPENAI),
        ("minimax-flash", LLMProvider.MINIMAX),
        ("mimo", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order)


def list_available_model_ids() -> list[str]:
    """Return distinct model IDs, alphabetically except MiniMax Flash before M3.

    Reflects the providers configured at process start (``AVAILABLE_MODELS``),
    which is fixed for the lifetime of a deployment.
    """
    ids = sorted({model.id for model in AVAILABLE_MODELS.values() if model.selectable})
    for flash, m3 in (
        ("minimax-flash", "minimax"),
        ("minimax/minimax-flash:free", "minimax/minimax"),
    ):
        if flash in ids and m3 in ids:
            first, second = sorted((ids.index(flash), ids.index(m3)))
            ids[first], ids[second] = flash, m3
    return ids
