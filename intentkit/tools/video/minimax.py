"""MiniMax Hailuo video generation tools (via OpenRouter)."""

from decimal import Decimal

from intentkit.tools.video.base import VideoBaseTool


class HailuoVideo(VideoBaseTool):
    """Generate videos using MiniMax H3.

    Keeps the ``video_hailuo`` name it had while backed by MiniMax's own
    Hailuo 2.3 endpoint, so agents that already enabled it keep the tool
    across the move to OpenRouter and the H3 model.
    """

    name: str = "video_hailuo"
    title: str = "MiniMax H3"
    description: str = (
        "Generate videos from text prompts or an input image using MiniMax H3. "
        "Omni-modal generation with native audio. Up to 2K."
    )
    # Fallback only: the real charge is metered from OpenRouter's reported
    # usage. See VideoBaseTool.
    price: Decimal = Decimal("800")
    openrouter_model: str = "minimax/hailuo-3"
