"""Tests for the cn_stock tool package."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools.base import ToolException
from pydantic import ValidationError

from intentkit.tools.cn_stock import get_tools
from intentkit.tools.cn_stock.base import (
    CNStockBaseTool,
    market_of,
    normalize_a_share_symbol,
)
from intentkit.tools.cn_stock.get_announcement import GetAnnouncement
from intentkit.tools.cn_stock.get_board import GetBoard, GetBoardInput
from intentkit.tools.cn_stock.get_capital_flow import (
    GetCapitalFlow,
    GetCapitalFlowInput,
)
from intentkit.tools.cn_stock.get_financials import GetFinancials
from intentkit.tools.cn_stock.get_index import GetIndex, GetIndexInput
from intentkit.tools.cn_stock.get_kline import GetKLine, GetKLineInput
from intentkit.tools.cn_stock.get_news import GetNews, GetNewsInput
from intentkit.tools.cn_stock.get_quote import GetQuote, GetQuoteInput
from intentkit.tools.cn_stock.is_trading_day import IsTradingDay


def test_tool_metadata():
    """Each tool exposes the expected name and shared category."""
    cases = [
        (GetQuote, "cn_stock_get_quote"),
        (GetKLine, "cn_stock_get_kline"),
        (GetIndex, "cn_stock_get_index"),
        (GetBoard, "cn_stock_get_board"),
        (GetCapitalFlow, "cn_stock_get_capital_flow"),
        (GetNews, "cn_stock_get_news"),
        (GetAnnouncement, "cn_stock_get_announcement"),
        (GetFinancials, "cn_stock_get_financials"),
        (IsTradingDay, "cn_stock_is_trading_day"),
    ]
    for cls, expected_name in cases:
        tool = cls()
        assert tool.name == expected_name
        assert tool.category == "cn_stock"


def test_normalize_symbol_accepts_common_formats():
    assert normalize_a_share_symbol("600519") == "600519"
    assert normalize_a_share_symbol("sh600519") == "600519"
    assert normalize_a_share_symbol("SH600519") == "600519"
    assert normalize_a_share_symbol("600519.SH") == "600519"
    assert normalize_a_share_symbol("600519.sh") == "600519"
    assert normalize_a_share_symbol("000001") == "000001"


def test_normalize_symbol_rejects_garbage():
    for bad in ["", "foo", "12345", "1234567", "abcdef", "60051X"]:
        with pytest.raises(ToolException):
            normalize_a_share_symbol(bad)


def test_market_of_classifies_correctly():
    assert market_of("600519") == "sh"
    assert market_of("000001") == "sz"
    assert market_of("300750") == "sz"
    assert market_of("430000") == "bj"
    assert market_of("830000") == "bj"
    assert market_of("920000") == "bj"  # BSE 920xxx prefix
    assert market_of("924000") == "bj"
    with pytest.raises(ToolException):
        market_of("100000")  # leading 1 is not a valid A-share prefix
    with pytest.raises(ToolException):
        market_of("900001")  # 900xxx is SSE B-shares, not A-shares


def test_quote_input_validation():
    GetQuoteInput(symbols=["600519"])
    with pytest.raises(ValidationError):
        GetQuoteInput(symbols=[])
    with pytest.raises(ValidationError):
        GetQuoteInput(symbols=["600519"] * 51)


def test_kline_input_defaults_and_bounds():
    inp = GetKLineInput(symbol="600519")
    assert inp.period == "daily"
    assert inp.days_back == 90
    assert inp.adjust == "qfq"
    with pytest.raises(ValidationError):
        GetKLineInput(symbol="600519", days_back=0)
    with pytest.raises(ValidationError):
        GetKLineInput(symbol="600519", days_back=2000)


def test_board_input_defaults():
    inp = GetBoardInput()
    assert inp.kind == "industry"
    assert inp.top == 20


def test_capital_flow_input_requires_symbol_for_stock():
    GetCapitalFlowInput(scope="market")
    GetCapitalFlowInput(scope="stock", symbol="600519")
    # Pydantic itself does not enforce the cross-field rule;
    # the runtime tool raises ToolException when scope='stock' has no symbol.


def test_news_input_basic():
    GetNewsInput(scope="macro")
    GetNewsInput(scope="stock", symbol="600519", limit=5)


def test_index_input_default_indices():
    inp = GetIndexInput()
    assert "上证指数" in inp.indices
    assert "沪深300" in inp.indices
    assert inp.history == "spot"


@pytest.mark.asyncio
async def test_get_tools_selects_by_name():
    """get_tools returns exactly the requested tools; unknown names are skipped."""
    requested = [
        "cn_stock_get_quote",
        "cn_stock_get_index",
        "cn_stock_is_trading_day",
        "cn_stock_nonexistent",
    ]
    tools = await get_tools(requested)
    names = [t.name for t in tools]
    assert names == [
        "cn_stock_get_quote",
        "cn_stock_get_index",
        "cn_stock_is_trading_day",
    ]

    assert await get_tools([]) == []


@pytest.mark.asyncio
async def test_quote_filters_to_requested_symbols():
    """GetQuote.run_blocking should be called with the right cache key, and the
    tool should filter the full-market dump down to the requested symbols only."""

    async def fake_run_blocking(self, *_args, **_kwargs):
        return [
            {"代码": "600519", "名称": "贵州茅台", "最新价": 1700.0},
            {"代码": "000001", "名称": "平安银行", "最新价": 11.0},
            {"代码": "300750", "名称": "宁德时代", "最新价": 200.0},
        ]

    with patch.object(CNStockBaseTool, "run_blocking", new=fake_run_blocking):
        tool = GetQuote()
        out = await tool._arun(symbols=["600519", "300750"])
        codes = {row["代码"] for row in out}
        assert codes == {"600519", "300750"}


@pytest.mark.asyncio
async def test_quote_raises_when_nothing_matches():
    async def empty_run_blocking(self, *_args, **_kwargs):
        return [
            {"代码": "999999", "名称": "Other", "最新价": 1.0},
        ]

    with patch.object(CNStockBaseTool, "run_blocking", new=empty_run_blocking):
        tool = GetQuote()
        with pytest.raises(ToolException):
            await tool._arun(symbols=["600519"])


@pytest.mark.asyncio
async def test_capital_flow_stock_requires_symbol_at_runtime():
    tool = GetCapitalFlow()
    with pytest.raises(ToolException):
        await tool._arun(scope="stock")


@pytest.mark.asyncio
async def test_index_rejects_unknown_name():
    tool = GetIndex()
    with pytest.raises(ToolException):
        await tool._arun(indices=["Made Up Index"])


@pytest.mark.asyncio
async def test_run_blocking_uses_redis_cache_when_present():
    """When cache_key is given, a cached payload should short-circuit the call."""
    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value='[{"a": 1}]')
    fake_redis.set = AsyncMock()
    sentinel = MagicMock(side_effect=AssertionError("must not be called on cache hit"))

    tool = GetQuote()
    with (
        patch("intentkit.tools.cn_stock.base.get_redis", return_value=fake_redis),
        patch.object(CNStockBaseTool, "global_rate_limit_by_category", new=AsyncMock()),
    ):
        result: Any = await tool.run_blocking("k", 30, sentinel)
    assert result == [{"a": 1}]
    sentinel.assert_not_called()


@pytest.mark.asyncio
async def test_run_blocking_skips_cache_when_key_is_none():
    """When cache_key is None the function is invoked directly, no Redis touch."""
    fake_redis = MagicMock()
    fake_redis.get = AsyncMock()

    def producer():
        return [{"x": 42}]

    tool = GetQuote()
    with (
        patch("intentkit.tools.cn_stock.base.get_redis", return_value=fake_redis),
        patch.object(CNStockBaseTool, "global_rate_limit_by_category", new=AsyncMock()),
    ):
        result = await tool.run_blocking(None, 0, producer)
    assert result == [{"x": 42}]
    fake_redis.get.assert_not_called()
