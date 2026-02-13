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
    # 2. GPT-5 Mini: High quality fallback
    # 3. GLM 4.7 Flash: Fast and cheap alternative
    # 4. Grok: Good performance if available
    # 5. DeepSeek: Final fallback
    order: list[tuple[str, LLMProvider]] = [
        ("google/gemini-3-flash-preview", LLMProvider.GOOGLE),
        ("gpt-5-mini", LLMProvider.OPENAI),
        ("z-ai/glm-4.7-flash", LLMProvider.OPENROUTER),
        ("grok-4-1-fast-non-reasoning", LLMProvider.XAI),
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

    raise RuntimeError("No summarize model available: missing all required API keys")


def pick_default_model() -> str:
    """
    Pick the best available default model for agents based on configured API keys.
    Used as the default_factory for the agent model field.
    """
    # Priority order based on general-purpose capability:
    # 1. Google Gemini 3 Flash: Best blend of speed and quality
    # 2. GPT-5 Mini: High quality fallback
    # 3. MiniMax M2.5: Good general-purpose via OpenRouter
    # 4. Grok: Good performance if available
    # 5. DeepSeek: Final fallback
    order: list[tuple[str, LLMProvider]] = [
        ("google/gemini-3-flash-preview", LLMProvider.GOOGLE),
        ("gpt-5-mini", LLMProvider.OPENAI),
        ("minimax/minimax-m2.5", LLMProvider.OPENROUTER),
        ("grok-4-1-fast-non-reasoning", LLMProvider.XAI),
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

    raise RuntimeError("No default model available: missing all required API keys")
