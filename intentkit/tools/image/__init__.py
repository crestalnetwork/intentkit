"""Image generation tools across multiple providers."""

from collections.abc import Callable

from intentkit.config.config import config as system_config
from intentkit.tools.image.base import ImageBaseTool
from intentkit.tools.image.gemini import (
    GeminiImageFlash,
    GeminiImageFlashLite,
    GeminiImagePro,
)
from intentkit.tools.image.gpt import GPTImageFlagship, GPTImageMini
from intentkit.tools.image.grok import GrokImage
from intentkit.tools.image.minimax import MiniMaxImage
from intentkit.tools.image.openrouter import FluxPro, Riverflow
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="Image Generation",
    description="Generate images from text prompts using multiple AI providers. Supports GPT, Gemini, Grok, FLUX, and Riverflow models with automatic API fallback to OpenRouter.",
    tags=["Media", "AI"],
    icon="/tools/image/image.svg",
)


# Cache tools at the system level, because they are stateless
_cache: dict[str, ImageBaseTool] = {}

_TOOL_NAME_TO_CLASS: dict[str, Callable[[], ImageBaseTool]] = {
    "image_gpt": GPTImageFlagship,
    "image_gpt_mini": GPTImageMini,
    "image_gemini_pro": GeminiImagePro,
    "image_gemini_flash": GeminiImageFlash,
    "image_gemini_flash_lite": GeminiImageFlashLite,
    "image_grok": GrokImage,
    "image_flux_pro": FluxPro,
    "image_riverflow": Riverflow,
    "image_minimax": MiniMaxImage,
}


async def get_tools(tool_names: list[str], **_) -> list[ImageBaseTool]:
    """Get the requested image generation tools; unknown names are skipped."""
    return [tool for name in tool_names if (tool := get_image_tool(name))]


def get_image_tool(tool_name: str) -> ImageBaseTool | None:
    """Get an image tool by name with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    cls = _TOOL_NAME_TO_CLASS.get(tool_name)
    if cls is None:
        return None

    _cache[tool_name] = cls()
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(
        system_config.openai_api_key
        or system_config.google_api_key
        or system_config.xai_api_key
        or system_config.openrouter_api_key
        or system_config.minimax_plan_api_key
    )
