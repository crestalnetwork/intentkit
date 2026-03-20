"""
Logic for selecting the best available LLM model for various tasks.
"""

from intentkit.config.config import config
from intentkit.models.llm import LLMProvider


def pick_summarize_model() -> str:
    """
    Pick the best available summarize model based on configured API keys.
    """
    # Priority order based on performance and cost effectiveness:
    # 1. Google Gemini 3 Flash: Best blend of speed and quality for summarization
    # 2. MiniMax M2.7 Highspeed: Fast and cheap native API
    # 3. GPT-5 Mini: High quality fallback
    # 4. GLM 4.7 Flash: Fast and cheap alternative
    # 5. Grok: Good performance if available
    # 6. DeepSeek: Final fallback
    order: list[tuple[str, LLMProvider]] = [
        ("z-ai/glm-4.7-flash", LLMProvider.OPENROUTER),
        ("gemini-3.1-flash-lite-preview", LLMProvider.GOOGLE),
        ("MiniMax-M2.7-highspeed", LLMProvider.MINIMAX),
        ("gpt-5-mini", LLMProvider.OPENAI),
        ("grok-4-1-fast-non-reasoning", LLMProvider.XAI),
        ("deepseek-chat", LLMProvider.DEEPSEEK),
    ]

    for model_id, provider in order:
        if provider == LLMProvider.OPENAI and config.openai_api_key:
            return model_id
        if provider == LLMProvider.GOOGLE and config.google_api_key:
            return model_id
        if provider == LLMProvider.MINIMAX and config.minimax_api_key:
            return model_id
        if provider == LLMProvider.OPENROUTER and config.openrouter_api_key:
            return model_id
        if provider == LLMProvider.XAI and config.xai_api_key:
            return model_id
        if provider == LLMProvider.DEEPSEEK and config.deepseek_api_key:
            return model_id

    raise RuntimeError("No summarize model available: missing all required API keys")


def pick_default_model() -> str:
    """
    Pick the best available default model for agents based on configured API keys.
    Used as the default_factory for the agent model field.
    """
    # Priority order based on general-purpose capability:
    # 1. MiniMax M2.7: Top intelligence, native API preferred
    # 2. Google Gemini 3 Flash: Best blend of speed and quality
    # 3. GPT-5 Mini: High quality fallback
    # 4. MiniMax M2.7 via OpenRouter: Good general-purpose fallback
    # 5. Grok: Good performance if available
    # 6. DeepSeek: Final fallback
    order: list[tuple[str, LLMProvider]] = [
        ("MiniMax-M2.7", LLMProvider.MINIMAX),
        ("google/gemini-3-flash-preview", LLMProvider.GOOGLE),
        ("gpt-5-mini", LLMProvider.OPENAI),
        ("minimax/minimax-m2.7", LLMProvider.OPENROUTER),
        ("grok-4-1-fast-non-reasoning", LLMProvider.XAI),
        ("deepseek-chat", LLMProvider.DEEPSEEK),
    ]

    for model_id, provider in order:
        if provider == LLMProvider.OPENAI and config.openai_api_key:
            return model_id
        if provider == LLMProvider.GOOGLE and config.google_api_key:
            return model_id
        if provider == LLMProvider.MINIMAX and config.minimax_api_key:
            return model_id
        if provider == LLMProvider.OPENROUTER and config.openrouter_api_key:
            return model_id
        if provider == LLMProvider.XAI and config.xai_api_key:
            return model_id
        if provider == LLMProvider.DEEPSEEK and config.deepseek_api_key:
            return model_id

    # Fallback to a reasonable default rather than crashing, since this is
    # also used as a SQLAlchemy column default for TemplateTable.
    return "gpt-5-mini"


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
        ("gpt-5-nano", LLMProvider.OPENAI),
        ("deepseek-chat", LLMProvider.DEEPSEEK),
    ]

    for model_id, provider in order:
        if provider == LLMProvider.OPENAI and config.openai_api_key:
            return model_id
        if provider == LLMProvider.GOOGLE and config.google_api_key:
            return model_id
        if provider == LLMProvider.OPENROUTER and config.openrouter_api_key:
            return model_id
        if provider == LLMProvider.XAI and config.xai_api_key:
            return model_id
        if provider == LLMProvider.DEEPSEEK and config.deepseek_api_key:
            return model_id

    raise RuntimeError("No long-context model available: missing all required API keys")
