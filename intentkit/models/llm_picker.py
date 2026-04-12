"""
Logic for selecting the best available LLM model for various tasks.
"""

from intentkit.config.config import config
from intentkit.models.llm import LLMProvider


def pick_summarize_model() -> str:
    """
    Pick the best available summarize model based on configured API keys.
    """
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-3.1-flash-lite-preview", LLMProvider.GOOGLE),
        ("z-ai/glm-4.7-flash", LLMProvider.OPENROUTER),
        ("gpt-5.4-mini", LLMProvider.OPENAI),
        ("grok-4-1-fast-non-reasoning", LLMProvider.XAI),
        ("deepseek-chat", LLMProvider.DEEPSEEK),
        ("MiniMax-M2.7", LLMProvider.MINIMAX),
    ]
    if (
        LLMProvider.OPENAI_COMPATIBLE.is_configured
        and config.openai_compatible_model_lite
    ):
        order.insert(
            0, (config.openai_compatible_model_lite, LLMProvider.OPENAI_COMPATIBLE)
        )
    if (
        LLMProvider.ANTHROPIC_COMPATIBLE.is_configured
        and config.anthropic_compatible_model_lite
    ):
        order.insert(
            0,
            (config.anthropic_compatible_model_lite, LLMProvider.ANTHROPIC_COMPATIBLE),
        )

    for model_id, provider in order:
        if provider.is_configured:
            return model_id

    raise RuntimeError("No summarize model available: missing all required API keys")


def pick_default_model() -> str:
    """
    Pick the best available default model for agents based on configured API keys.
    Used as the default_factory for the agent model field.
    """
    order: list[tuple[str, LLMProvider]] = [
        ("google/gemini-3-flash-preview", LLMProvider.GOOGLE),
        ("MiniMax-M2.7", LLMProvider.MINIMAX),
        ("minimax/minimax-m2.7", LLMProvider.OPENROUTER),
        ("gpt-5.4-mini", LLMProvider.OPENAI),
        ("grok-4-1-fast-non-reasoning", LLMProvider.XAI),
        ("deepseek-chat", LLMProvider.DEEPSEEK),
    ]
    if LLMProvider.OPENAI_COMPATIBLE.is_configured and config.openai_compatible_model:
        order.insert(1, (config.openai_compatible_model, LLMProvider.OPENAI_COMPATIBLE))
    if (
        LLMProvider.ANTHROPIC_COMPATIBLE.is_configured
        and config.anthropic_compatible_model
    ):
        order.insert(
            1, (config.anthropic_compatible_model, LLMProvider.ANTHROPIC_COMPATIBLE)
        )

    for model_id, provider in order:
        if provider.is_configured:
            return model_id

    # Fallback to a reasonable default rather than crashing, since this is
    # also used as a SQLAlchemy column default for TemplateTable.
    return "gpt-5.4-mini"


def pick_tool_selector_model() -> str | None:
    """
    Pick the best available model for LLM-based tool selection.

    Returns None when no suitable model is available, so the caller can
    skip the tool-selector middleware gracefully.

    Tool selection uses `response_format: json_schema` structured output.
    Only OpenAI models are known to handle the LangChain
    LLMToolSelectorMiddleware schema reliably (see langchain-ai/langchain
    #33651, #24225 for Gemini/GLM incompatibilities).
    """
    order: list[tuple[str, LLMProvider]] = [
        ("gpt-5.4-nano", LLMProvider.OPENAI),
        ("openai/gpt-5.4-nano", LLMProvider.OPENROUTER),
    ]

    for model_id, provider in order:
        if provider.is_configured:
            return model_id

    return None


def pick_long_context_model() -> str:
    """
    Pick the cheapest available model with context length >= 1,000,000 tokens.
    Falls back to any available model if no long-context model is configured.
    """
    # Priority order based on cost (cheapest first), one per provider:
    order: list[tuple[str, LLMProvider]] = [
        ("gemini-3.1-flash-lite-preview", LLMProvider.GOOGLE),
        ("grok-4-1-fast-non-reasoning", LLMProvider.XAI),
        ("qwen/qwen3.5-flash-02-23", LLMProvider.OPENROUTER),
        ("gpt-5.4-nano", LLMProvider.OPENAI),
        ("deepseek-chat", LLMProvider.DEEPSEEK),
        ("MiniMax-M2.7", LLMProvider.MINIMAX),
    ]
    if LLMProvider.OPENAI_COMPATIBLE.is_configured and config.openai_compatible_model:
        order.append((config.openai_compatible_model, LLMProvider.OPENAI_COMPATIBLE))
    if (
        LLMProvider.ANTHROPIC_COMPATIBLE.is_configured
        and config.anthropic_compatible_model
    ):
        order.append(
            (config.anthropic_compatible_model, LLMProvider.ANTHROPIC_COMPATIBLE)
        )

    for model_id, provider in order:
        if provider.is_configured:
            return model_id

    raise RuntimeError("No long-context model available: missing all required API keys")
