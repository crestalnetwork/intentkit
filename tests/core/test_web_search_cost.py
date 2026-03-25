"""Tests for per-provider web search cost calculation."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from intentkit.core.engine import count_web_searches
from intentkit.models.llm import LLMProvider, calculate_search_cost

# --- count_web_searches tests ---


class TestCountWebSearchesOpenAI:
    def test_single_web_search_call(self):
        msg = SimpleNamespace(
            additional_kwargs={
                "tool_outputs": [{"type": "web_search_call", "id": "ws_1"}]
            },
            response_metadata={},
        )
        assert count_web_searches(msg, LLMProvider.OPENAI) == 1

    def test_multiple_web_search_calls(self):
        msg = SimpleNamespace(
            additional_kwargs={
                "tool_outputs": [
                    {"type": "web_search_call", "id": "ws_1"},
                    {"type": "web_search_call", "id": "ws_2"},
                    {"type": "web_search_call", "id": "ws_3"},
                ]
            },
            response_metadata={},
        )
        assert count_web_searches(msg, LLMProvider.OPENAI) == 3

    def test_no_web_search_calls(self):
        msg = SimpleNamespace(
            additional_kwargs={"tool_outputs": [{"type": "other_tool"}]},
            response_metadata={},
        )
        assert count_web_searches(msg, LLMProvider.OPENAI) == 0

    def test_empty_additional_kwargs(self):
        msg = SimpleNamespace(additional_kwargs={}, response_metadata={})
        assert count_web_searches(msg, LLMProvider.OPENAI) == 0

    def test_no_additional_kwargs(self):
        msg = SimpleNamespace(response_metadata={})
        assert count_web_searches(msg, LLMProvider.OPENAI) == 0


class TestCountWebSearchesGoogle:
    def test_grounding_metadata_snake_case(self):
        msg = SimpleNamespace(
            additional_kwargs={
                "grounding_metadata": {"web_search_queries": ["query1", "query2"]}
            },
            response_metadata={},
        )
        assert count_web_searches(msg, LLMProvider.GOOGLE) == 2

    def test_grounding_metadata_camel_case(self):
        msg = SimpleNamespace(
            additional_kwargs={"groundingMetadata": {"webSearchQueries": ["query1"]}},
            response_metadata={},
        )
        assert count_web_searches(msg, LLMProvider.GOOGLE) == 1

    def test_grounding_in_response_metadata(self):
        msg = SimpleNamespace(
            additional_kwargs={},
            response_metadata={
                "grounding_metadata": {"web_search_queries": ["q1", "q2", "q3"]}
            },
        )
        assert count_web_searches(msg, LLMProvider.GOOGLE) == 3

    def test_no_grounding_metadata(self):
        msg = SimpleNamespace(additional_kwargs={}, response_metadata={})
        assert count_web_searches(msg, LLMProvider.GOOGLE) == 0

    def test_empty_queries_list(self):
        msg = SimpleNamespace(
            additional_kwargs={"grounding_metadata": {"web_search_queries": []}},
            response_metadata={},
        )
        assert count_web_searches(msg, LLMProvider.GOOGLE) == 0


class TestCountWebSearchesXAI:
    def test_web_search_count(self):
        msg = SimpleNamespace(
            additional_kwargs={},
            response_metadata={"server_side_tool_usage": {"web_search": 3}},
        )
        assert count_web_searches(msg, LLMProvider.XAI) == 3

    def test_x_search_count(self):
        msg = SimpleNamespace(
            additional_kwargs={},
            response_metadata={"server_side_tool_usage": {"x_search": 2}},
        )
        assert count_web_searches(msg, LLMProvider.XAI) == 2

    def test_combined_search_counts(self):
        msg = SimpleNamespace(
            additional_kwargs={},
            response_metadata={
                "server_side_tool_usage": {"web_search": 2, "x_search": 1}
            },
        )
        assert count_web_searches(msg, LLMProvider.XAI) == 3

    def test_non_search_tools_ignored(self):
        msg = SimpleNamespace(
            additional_kwargs={},
            response_metadata={
                "server_side_tool_usage": {
                    "web_search": 1,
                    "code_execution": 2,
                }
            },
        )
        assert count_web_searches(msg, LLMProvider.XAI) == 1

    def test_no_server_side_tool_usage(self):
        msg = SimpleNamespace(additional_kwargs={}, response_metadata={})
        assert count_web_searches(msg, LLMProvider.XAI) == 0


class TestCountWebSearchesOpenRouter:
    def test_always_returns_zero(self):
        msg = SimpleNamespace(
            additional_kwargs={"tool_outputs": [{"type": "web_search_call"}]},
            response_metadata={},
        )
        assert count_web_searches(msg, LLMProvider.OPENROUTER) == 0


# --- calculate_search_cost tests ---


@pytest.mark.asyncio
class TestCalculateSearchCost:
    @patch("intentkit.models.llm.AppSetting")
    async def test_openai_cost(self, mock_app_setting):
        """Test OpenAI search cost: 3500 * 1 * 0.01 = 35."""
        import intentkit.models.llm as llm_module

        llm_module.credit_per_usdc = None

        mock_payment = AsyncMock()
        mock_payment.credit_per_usdc = Decimal("3500")
        mock_app_setting.payment = AsyncMock(return_value=mock_payment)

        cost = await calculate_search_cost(LLMProvider.OPENAI, 1)
        assert cost == Decimal("35.0000")

        llm_module.credit_per_usdc = None

    @patch("intentkit.models.llm.AppSetting")
    async def test_xai_multiple_searches(self, mock_app_setting):
        """Test xAI search cost: 3500 * 3 * 0.005 = 52.5."""
        import intentkit.models.llm as llm_module

        llm_module.credit_per_usdc = None

        mock_payment = AsyncMock()
        mock_payment.credit_per_usdc = Decimal("3500")
        mock_app_setting.payment = AsyncMock(return_value=mock_payment)

        cost = await calculate_search_cost(LLMProvider.XAI, 3)
        assert cost == Decimal("52.5000")

        llm_module.credit_per_usdc = None

    async def test_openrouter_no_charge(self):
        """OpenRouter has no search price — should return 0."""
        cost = await calculate_search_cost(LLMProvider.OPENROUTER, 5)
        assert cost == Decimal("0")

    async def test_zero_count(self):
        cost = await calculate_search_cost(LLMProvider.OPENAI, 0)
        assert cost == Decimal("0")
