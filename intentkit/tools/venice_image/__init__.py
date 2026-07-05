"""Venice Image generation and analysis tools."""

from intentkit.config.config import config as system_config
from intentkit.tools.meta import ToolsetMeta

# Import the base tool and all specific model tool classes
from intentkit.tools.venice_image.base import VeniceImageBaseTool
from intentkit.tools.venice_image.image_enhance.image_enhance import ImageEnhance
from intentkit.tools.venice_image.image_generation.image_generation_fluently_xl import (
    ImageGenerationFluentlyXL,
)
from intentkit.tools.venice_image.image_generation.image_generation_flux_dev import (
    ImageGenerationFluxDev,
)
from intentkit.tools.venice_image.image_generation.image_generation_flux_dev_uncensored import (
    ImageGenerationFluxDevUncensored,
)
from intentkit.tools.venice_image.image_generation.image_generation_lustify_sdxl import (
    ImageGenerationLustifySDXL,
)
from intentkit.tools.venice_image.image_generation.image_generation_pony_realism import (
    ImageGenerationPonyRealism,
)
from intentkit.tools.venice_image.image_generation.image_generation_stable_diffusion_3_5 import (
    ImageGenerationStableDiffusion35,
)
from intentkit.tools.venice_image.image_generation.image_generation_venice_sd35 import (
    ImageGenerationVeniceSD35,
)
from intentkit.tools.venice_image.image_upscale.image_upscale import ImageUpscale
from intentkit.tools.venice_image.image_vision.image_vision import ImageVision

toolset = ToolsetMeta(
    title="Venice Image",
    description="Tools for generating images using the Venice AI API.",
    tags=["AI", "Image"],
    icon="/tools/venice_image/venice_image.jpg",
)


# Cache tools at the system level, because they are stateless
_cache: dict[str, VeniceImageBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[VeniceImageBaseTool]] = {
    "venice_image_upscale": ImageUpscale,
    "venice_image_enhance": ImageEnhance,
    "venice_image_vision": ImageVision,
    "venice_image_generation_flux_dev": ImageGenerationFluxDev,
    "venice_image_generation_flux_dev_uncensored": ImageGenerationFluxDevUncensored,
    "venice_image_generation_venice_sd35": ImageGenerationVeniceSD35,
    "venice_image_generation_fluently_xl": ImageGenerationFluentlyXL,
    "venice_image_generation_lustify_sdxl": ImageGenerationLustifySDXL,
    "venice_image_generation_pony_realism": ImageGenerationPonyRealism,
    "venice_image_generation_stable_diffusion_3_5": ImageGenerationStableDiffusion35,
}


async def get_tools(tool_names: list[str], **_) -> list[VeniceImageBaseTool]:
    """Return Venice Image tool instances for the requested names.

    Unknown names are skipped silently.
    """
    tools: list[VeniceImageBaseTool] = []
    for name in tool_names:
        tool = get_venice_image_tool(name)
        if tool:
            tools.append(tool)
    return tools


def get_venice_image_tool(tool_name: str) -> VeniceImageBaseTool | None:
    """Get a Venice Image tool by name, with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        return None

    _cache[tool_name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.venice_api_key)
