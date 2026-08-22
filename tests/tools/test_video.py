"""Tests for video generation tools."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openrouter.components import VideoGenerationResponse, VideoGenerationUsage

from intentkit.tools import base as tool_base
from intentkit.tools.video import get_tools
from intentkit.tools.video.base import usage_cost_usd
from intentkit.tools.video.minimax import HailuoVideo
from intentkit.tools.video.seedance import SeedanceMiniVideo, SeedanceVideo


@pytest.fixture(autouse=True)
def clear_metered_costs():
    """The metered-cost registry is process-global; don't leak across tests."""
    tool_base._metered_tool_costs.clear()
    yield
    tool_base._metered_tool_costs.clear()


def test_tool_metadata():
    """Test tool names, fallback prices, models, and categories."""
    cases = [
        (
            SeedanceMiniVideo,
            "video_seedance_mini",
            Decimal("500"),
            "bytedance/seedance-2.0-mini",
        ),
        (SeedanceVideo, "video_seedance", Decimal("1500"), "bytedance/seedance-2.5"),
        (HailuoVideo, "video_hailuo", Decimal("800"), "minimax/hailuo-3"),
    ]
    for cls, expected_name, expected_price, expected_model in cases:
        tool = cls()
        assert tool.name == expected_name
        assert tool.price == expected_price
        assert tool.openrouter_model == expected_model
        assert tool.category == "video"
        assert tool.response_format == "content_and_artifact"


@pytest.mark.asyncio
async def test_get_tools_selects_by_name():
    """get_tools returns exactly the requested tools; unknown names — the
    retired video_sora/video_veo/video_grok among them — are skipped."""
    tools = await get_tools(["video_seedance", "video_sora", "video_hailuo"])
    names = [t.name for t in tools]
    assert names == ["video_seedance", "video_hailuo"]

    assert await get_tools([]) == []


def test_migration_strips_exactly_the_removed_names():
    """The strip migration's list must track the tools actually removed: a
    name left off lingers in pickers, and a live tool listed gets un-enabled."""
    from intentkit.migrations.versions.a4e7c2f9b6d3_strip_retired_video_tool_names import (
        _NAMES,
    )
    from intentkit.tools.video import _TOOL_NAME_TO_CLASS

    assert not set(_NAMES) & set(_TOOL_NAME_TO_CLASS), (
        "migration would strip a tool that still exists"
    )
    assert "video_hailuo" not in _NAMES, "video_hailuo kept its name across the move"


def test_availability_follows_openrouter_key():
    """Every model routes through OpenRouter, so one key gates them all."""
    tool = SeedanceVideo()
    with patch("intentkit.tools.video.base.config") as mock_config:
        mock_config.openrouter_api_key = "sk-or-test"
        assert tool.available()
        mock_config.openrouter_api_key = None
        assert not tool.available()


def test_first_frame_image_keeps_its_real_mime():
    """A JPEG first frame must not be shipped labelled as PNG."""
    jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64
    frames = SeedanceVideo()._frame_images(jpeg)
    assert frames is not None
    assert frames[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert frames[0]["frame_type"] == "first_frame"

    assert SeedanceVideo()._frame_images(None) is None


class TestUsageCostExtraction:
    """Reading the cost off a real SDK response, not a mock.

    The SDK's ``OptionalNullable`` fields default to an ``Unset()`` sentinel
    rather than ``None``. Mocking ``_generate`` hides that entirely, which is
    how an omitted cost came to raise and destroy an already-paid-for video.
    """

    @staticmethod
    def _job(usage) -> VideoGenerationResponse:
        return VideoGenerationResponse(
            id="job-1", polling_url="https://example/x", status="completed", usage=usage
        )

    def test_reported_cost_is_read(self):
        job = self._job(VideoGenerationUsage(cost=0.42))
        assert usage_cost_usd(job) == Decimal("0.42")

    def test_unset_cost_is_not_a_cost(self):
        """An omitted usage.cost is Unset(), which is neither None nor numeric."""
        usage = VideoGenerationUsage()
        # The trap this guards: Unset() passes an is-not-None test, and
        # Decimal(str(Unset())) raises InvalidOperation.
        assert usage.cost is not None
        assert usage_cost_usd(self._job(usage)) is None

    def test_null_cost_is_not_a_cost(self):
        assert usage_cost_usd(self._job(VideoGenerationUsage(cost=None))) is None

    def test_missing_usage_block_is_not_a_cost(self):
        assert usage_cost_usd(self._job(None)) is None

    def test_zero_cost_is_still_a_cost(self):
        """A free generation must bill 0, not fall back to the flat price."""
        assert usage_cost_usd(self._job(VideoGenerationUsage(cost=0))) == Decimal("0")


class TestMetering:
    """The provider's reported usage — not the flat price — is what gets billed."""

    @staticmethod
    async def _invoke(tool, usd: Decimal | None, call_id: str):
        """Drive the tool the way the agent's tool node does: a tool_call dict.

        ``tool_call_id`` is deliberately absent from ``args_schema`` (the model
        must not supply it), so only the ``InjectedToolCallId`` annotation
        makes it arrive — and only this invocation path carries an id at all.
        """
        payload: dict = {
            "name": tool.name,
            "args": {"prompt": "a cat"},
            "id": call_id,
            "type": "tool_call",
        }
        with (
            patch.object(
                type(tool), "_generate", AsyncMock(return_value=(b"mp4", usd))
            ),
            patch.object(
                type(tool), "_upload_and_return", AsyncMock(return_value=("ok", []))
            ),
            patch.object(
                type(tool),
                "get_context",
                MagicMock(return_value=MagicMock(agent_id="a")),
            ),
        ):
            return await tool.ainvoke(payload)

    @pytest.mark.asyncio
    async def test_reported_cost_is_billable_against_the_call(self):
        await self._invoke(SeedanceVideo(), Decimal("0.25"), "tc-abc123")
        assert tool_base.take_tool_cost_usd("tc-abc123") == Decimal("0.25")

    @pytest.mark.asyncio
    async def test_job_without_a_usage_figure_falls_back_to_flat_price(self):
        await self._invoke(SeedanceVideo(), None, "tc-nousage")
        assert tool_base.take_tool_cost_usd("tc-nousage") is None

    @pytest.mark.asyncio
    async def test_a_call_id_is_never_optional_in_practice(self):
        """Metering cannot be silently skipped: LangChain refuses to run a
        tool carrying InjectedToolCallId unless it is given a full ToolCall,
        so every production invocation arrives with an id to bill against."""
        with pytest.raises(ValueError, match="InjectedToolCallId"):
            await SeedanceVideo().ainvoke({"prompt": "a cat"})
