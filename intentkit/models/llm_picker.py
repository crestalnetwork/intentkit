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
_DEFAULT_FALLBACK_MODEL = "gpt-5.6-luna"


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
        ("gemini-3.5-flash-lite", LLMProvider.GOOGLE),
        ("deepseek/deepseek-v4-flash-0731", LLMProvider.OPENROUTER),
        ("gpt-5.6-luna", LLMProvider.OPENAI),
        ("grok-4.5", LLMProvider.XAI),
        ("deepseek-v4-flash", LLMProvider.DEEPSEEK),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("mimo-v2.5", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, lite_compatible=True)


def pick_default_model() -> str:
    """Pick the best available default model for agents.

    Used as the ``default_factory`` for the agent model field, so it must never
    crash — it falls back to a reasonable model when nothing is configured.
    """
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-3.6-flash", LLMProvider.GOOGLE),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("minimax/minimax-m3", LLMProvider.OPENROUTER),
        ("gpt-5.6-luna", LLMProvider.OPENAI),
        ("grok-4.5", LLMProvider.XAI),
        ("deepseek-v4-flash", LLMProvider.DEEPSEEK),
        ("mimo-v2.5", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_lead_model() -> str:
    """Pick the model for the team lead orchestrator.

    The lead drives user conversation and multi-agent delegation. DeepSeek's
    V4 Flash 0731 build tops agent/tool-driving benchmarks at flash cost, so
    it heads the list on both its providers.
    """
    order: list[tuple[str, LLMProvider]] = [
        ("deepseek-v4-flash", LLMProvider.DEEPSEEK),
        ("deepseek/deepseek-v4-flash-0731", LLMProvider.OPENROUTER),
        ("gemini-3.6-flash", LLMProvider.GOOGLE),
        ("gpt-5.6-luna", LLMProvider.OPENAI),
        ("grok-4.5", LLMProvider.XAI),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("mimo-v2.5", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_lite_model() -> str:
    """Pick the cheapest/fastest "lite" model — good enough for simple tasks."""
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-3.5-flash-lite", LLMProvider.GOOGLE),
        ("z-ai/glm-4.7-flash", LLMProvider.OPENROUTER),
        ("deepseek-v4-flash", LLMProvider.DEEPSEEK),
        # Luna is OpenAI's cheapest tier; glm/deepseek above are still cheaper.
        ("gpt-5.6-luna", LLMProvider.OPENAI),
        ("grok-4.5", LLMProvider.XAI),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("mimo-v2.5", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(
        order, lite_compatible=True, fallback=_DEFAULT_FALLBACK_MODEL
    )


def pick_smartest_model() -> str:
    """Pick the highest-intelligence model for complex reasoning."""
    order: list[tuple[str, LLMProvider]] = [
        ("anthropic/claude-opus-5", LLMProvider.OPENROUTER),
        ("gemini-3.1-pro-preview-customtools", LLMProvider.GOOGLE),
        ("gpt-5.6-sol", LLMProvider.OPENAI),
        ("grok-4.5", LLMProvider.XAI),
        ("deepseek-v4-pro", LLMProvider.DEEPSEEK),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("mimo-v2.5-pro", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_fastest_model() -> str:
    """Pick the lowest-latency model for snappy, simple interactions."""
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-3.5-flash-lite", LLMProvider.GOOGLE),
        ("qwen/qwen3.7-flash", LLMProvider.OPENROUTER),
        ("gpt-5.6-luna", LLMProvider.OPENAI),
        ("grok-4.5", LLMProvider.XAI),
        ("deepseek-v4-flash", LLMProvider.DEEPSEEK),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("mimo-v2.5", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(
        order, lite_compatible=True, fallback=_DEFAULT_FALLBACK_MODEL
    )


def pick_multimodal_model() -> str:
    """Pick the best model that accepts image/audio/video input."""
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-3.6-flash", LLMProvider.GOOGLE),
        ("google/gemini-3.6-flash", LLMProvider.OPENROUTER),
        ("mimo-v2.5", LLMProvider.MIMO_PLAN),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("gpt-5.6-terra", LLMProvider.OPENAI),
        ("grok-4.5", LLMProvider.XAI),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_writing_model() -> str:
    """Pick the best model for high-quality general (English) writing."""
    order: list[tuple[str, LLMProvider]] = [
        ("anthropic/claude-sonnet-5", LLMProvider.OPENROUTER),
        ("gemini-3.1-pro-preview-customtools", LLMProvider.GOOGLE),
        ("gpt-5.6-sol", LLMProvider.OPENAI),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("deepseek-v4-pro", LLMProvider.DEEPSEEK),
        ("grok-4.5", LLMProvider.XAI),
        ("mimo-v2.5-pro", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_chinese_writing_model() -> str:
    """Pick the best model for Chinese writing (Chinese-native models first)."""
    order: list[tuple[str, LLMProvider]] = [
        ("qwen/qwen3.7-max", LLMProvider.OPENROUTER),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("mimo-v2.5-pro", LLMProvider.MIMO_PLAN),
        ("deepseek-v4-pro", LLMProvider.DEEPSEEK),
        ("gemini-3.1-pro-preview-customtools", LLMProvider.GOOGLE),
        ("gpt-5.6-sol", LLMProvider.OPENAI),
        ("grok-4.5", LLMProvider.XAI),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_finance_model() -> str:
    """Pick the best model for financial/quantitative analysis."""
    order: list[tuple[str, LLMProvider]] = [
        ("anthropic/claude-opus-5", LLMProvider.OPENROUTER),
        ("deepseek-v4-pro", LLMProvider.DEEPSEEK),
        ("gemini-3.1-pro-preview-customtools", LLMProvider.GOOGLE),
        ("gpt-5.6-sol", LLMProvider.OPENAI),
        ("grok-4.5", LLMProvider.XAI),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("mimo-v2.5-pro", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_search_model() -> str:
    """Pick the best model for web/realtime search (native-search providers first)."""
    order: list[tuple[str, LLMProvider]] = [
        ("grok-4.5", LLMProvider.XAI),
        ("gemini-3.6-flash", LLMProvider.GOOGLE),
        ("gpt-5.6-terra", LLMProvider.OPENAI),
        ("x-ai/grok-4.5", LLMProvider.OPENROUTER),
        ("deepseek-v4-flash", LLMProvider.DEEPSEEK),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("mimo-v2.5", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_broadest_knowledge_model() -> str:
    """Pick the model with the broadest world knowledge."""
    order: list[tuple[str, LLMProvider]] = [
        ("anthropic/claude-opus-5", LLMProvider.OPENROUTER),
        ("gemini-3.1-pro-preview-customtools", LLMProvider.GOOGLE),
        ("gpt-5.6-sol", LLMProvider.OPENAI),
        ("grok-4.5", LLMProvider.XAI),
        ("deepseek-v4-pro", LLMProvider.DEEPSEEK),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("mimo-v2.5-pro", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order, fallback=_DEFAULT_FALLBACK_MODEL)


def pick_long_context_model() -> str:
    """
    Pick the cheapest available model with context length >= 1,000,000 tokens.
    Falls back to any available model if no long-context model is configured.
    """
    # Priority order based on cost (cheapest first), one per provider:
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-3.5-flash-lite", LLMProvider.GOOGLE),
        ("deepseek/deepseek-v4-flash-0731", LLMProvider.OPENROUTER),
        ("deepseek-v4-flash", LLMProvider.DEEPSEEK),
        ("gpt-5.6-luna", LLMProvider.OPENAI),
        ("MiniMax-M3", LLMProvider.MINIMAX),
        ("mimo-v2.5", LLMProvider.MIMO_PLAN),
    ]
    return _first_configured(order)


def list_available_model_ids() -> list[str]:
    """Return the sorted, distinct model IDs available in this deployment.

    Reflects the providers configured at process start (``AVAILABLE_MODELS``),
    which is fixed for the lifetime of a deployment.
    """
    return sorted({model.id for model in AVAILABLE_MODELS.values()})
