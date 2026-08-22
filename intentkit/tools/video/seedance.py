"""ByteDance Seedance video generation tools (via OpenRouter)."""

from decimal import Decimal

from intentkit.tools.video.base import VideoBaseTool


class SeedanceMiniVideo(VideoBaseTool):
    """Generate videos using Seedance 2.0 Mini."""

    name: str = "video_seedance_mini"
    title: str = "Seedance 2.0 Mini"
    description: str = (
        "Generate videos from text prompts or an input image using ByteDance "
        "Seedance 2.0 Mini. The cheap, fast option — use it for drafts and "
        "quick iteration. Up to 720p."
    )
    # Fallback only: the real charge is metered from OpenRouter's reported
    # usage. See VideoBaseTool.
    price: Decimal = Decimal("500")
    openrouter_model: str = "bytedance/seedance-2.0-mini"


class SeedanceVideo(VideoBaseTool):
    """Generate videos using Seedance 2.5."""

    name: str = "video_seedance"
    title: str = "Seedance 2.5"
    description: str = (
        "Generate videos from text prompts or an input image using ByteDance "
        "Seedance 2.5. Best for long-form storytelling and reference-based "
        "generation. Up to 720p."
    )
    # Fallback only: the real charge is metered from OpenRouter's reported
    # usage. See VideoBaseTool.
    price: Decimal = Decimal("1500")
    openrouter_model: str = "bytedance/seedance-2.5"
