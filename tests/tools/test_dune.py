"""Tests for Dune tools."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from intentkit.tools.dune import available, get_tools
from intentkit.tools.dune.execute_query import DuneExecuteQuery, DuneExecuteQueryInput
from intentkit.tools.dune.get_query_results import (
    DuneGetQueryResults,
    DuneGetQueryResultsInput,
)
from intentkit.tools.dune.run_sql import DuneRunSQL, DuneRunSQLInput


def test_tool_metadata():
    """Test tool names, prices, and categories."""
    cases = [
        (DuneExecuteQuery, "dune_execute_query", Decimal("20")),
        (DuneGetQueryResults, "dune_get_query_results", Decimal("5")),
        (DuneRunSQL, "dune_run_sql", Decimal("30")),
    ]
    for cls, expected_name, expected_price in cases:
        tool = cls()
        assert tool.name == expected_name
        assert tool.price == expected_price
        assert tool.category == "dune"


def test_execute_query_input_valid():
    """Test DuneExecuteQueryInput accepts valid inputs."""
    inp = DuneExecuteQueryInput(query_id=12345)
    assert inp.query_id == 12345
    assert inp.parameters is None
    assert inp.limit == 100


def test_execute_query_input_with_params():
    """Test DuneExecuteQueryInput with parameters."""
    inp = DuneExecuteQueryInput(
        query_id=42,
        parameters={"chain": "ethereum", "days": "7"},
        limit=500,
    )
    assert inp.query_id == 42
    assert inp.parameters == {"chain": "ethereum", "days": "7"}
    assert inp.limit == 500


def test_execute_query_input_invalid_limit():
    """Test DuneExecuteQueryInput rejects out-of-range limits."""
    with pytest.raises(Exception):
        DuneExecuteQueryInput(query_id=1, limit=0)
    with pytest.raises(Exception):
        DuneExecuteQueryInput(query_id=1, limit=1001)


def test_get_query_results_input_valid():
    """Test DuneGetQueryResultsInput accepts valid inputs."""
    inp = DuneGetQueryResultsInput(query_id=99)
    assert inp.query_id == 99
    assert inp.limit == 100
    assert inp.offset == 0


def test_get_query_results_input_with_offset():
    """Test DuneGetQueryResultsInput with offset."""
    inp = DuneGetQueryResultsInput(query_id=99, limit=50, offset=200)
    assert inp.limit == 50
    assert inp.offset == 200


def test_run_sql_input_valid():
    """Test DuneRunSQLInput accepts valid inputs."""
    inp = DuneRunSQLInput(sql="SELECT * FROM ethereum.transactions LIMIT 10")
    assert inp.sql == "SELECT * FROM ethereum.transactions LIMIT 10"
    assert inp.limit == 100


def test_format_results_with_rows():
    """Test _format_results produces expected output."""
    tool = DuneExecuteQuery()
    result_json = {
        "result": {
            "metadata": {
                "column_names": ["block", "tx_hash", "value"],
                "executed_at": "2025-01-01T00:00:00Z",
                "total_row_count": 2,
            },
            "rows": [
                {"block": 100, "tx_hash": "0xabc", "value": 1.5},
                {"block": 101, "tx_hash": "0xdef", "value": 2.0},
            ],
        }
    }
    output = tool.format_results(result_json, 42)
    assert "Query 42 results" in output
    assert "2 rows" in output
    assert "block | tx_hash | value" in output
    assert "100 | 0xabc | 1.5" in output
    assert "101 | 0xdef | 2.0" in output


def test_format_results_no_rows():
    """Test _format_results with empty result set."""
    tool = DuneExecuteQuery()
    result_json = {
        "result": {
            "metadata": {
                "column_names": ["id"],
                "executed_at": "2025-01-01T00:00:00Z",
                "total_row_count": 0,
            },
            "rows": [],
        }
    }
    output = tool.format_results(result_json, 1)
    assert "No rows returned" in output


def test_format_results_truncation():
    """Test _format_results truncates at character limit."""
    tool = DuneExecuteQuery()
    rows = [{"col": "x" * 200} for _ in range(100)]
    result_json = {
        "result": {
            "metadata": {
                "column_names": ["col"],
                "executed_at": "2025-01-01T00:00:00Z",
                "total_row_count": 100,
            },
            "rows": rows,
        }
    }
    output = tool.format_results(result_json, 1)
    assert "truncated" in output
    assert len(output) < 5000


def test_available_with_key():
    """Test available() returns True when API key is set."""
    with patch("intentkit.tools.dune.system_config") as mock_config:
        mock_config.dune_api_key = "test-key"
        assert available() is True


def test_available_without_key():
    """Test available() returns False when API key is not set."""
    with patch("intentkit.tools.dune.system_config") as mock_config:
        mock_config.dune_api_key = ""
        assert available() is False


@pytest.mark.asyncio
async def test_get_tools_selects_by_name():
    """get_tools returns exactly the requested tools; unknown names are skipped."""
    tools = await get_tools(["dune_execute_query", "dune_run_sql", "dune_bogus"])
    names = [t.name for t in tools]
    assert names == ["dune_execute_query", "dune_run_sql"]

    assert await get_tools([]) == []
