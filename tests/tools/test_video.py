"""Tests for video generation tools."""

from decimal import Decimal

import pytest

from intentkit.tools.video import get_tools
from intentkit.tools.video.gemini import VeoVideo, VeoVideoFast
from intentkit.tools.video.gpt import SoraVideo, SoraVideoPro
from intentkit.tools.video.grok import GrokVideo
from intentkit.tools.video.minimax import HailuoVideo


def test_tool_metadata():
    """Test tool names, prices, and categories."""
    cases = [
        (GrokVideo, "video_grok", Decimal("800")),
        (SoraVideo, "video_sora", Decimal("1000")),
        (SoraVideoPro, "video_sora_pro", Decimal("3000")),
        (VeoVideo, "video_veo", Decimal("3200")),
        (VeoVideoFast, "video_veo_fast", Decimal("1200")),
        (HailuoVideo, "video_hailuo", Decimal("500")),
    ]
    for cls, expected_name, expected_price in cases:
        tool = cls()
        assert tool.name == expected_name
        assert tool.price == expected_price
        assert tool.category == "video"
        assert tool.response_format == "content_and_artifact"


@pytest.mark.asyncio
async def test_get_tools_selects_by_name():
    """get_tools returns exactly the requested tools; unknown names are skipped."""
    tools = await get_tools(["video_grok", "video_veo", "video_bogus"])
    names = [t.name for t in tools]
    assert names == ["video_grok", "video_veo"]

    assert await get_tools([]) == []
