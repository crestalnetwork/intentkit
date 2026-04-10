"""Tests for the long-term memory system."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.memory import MAX_MEMORY_BYTES, update_memory


@pytest.fixture
def mock_agent_data():
    """Fixture for mocked AgentData."""
    agent_data = MagicMock()
    agent_data.long_term_memory = None
    return agent_data


@pytest.fixture
def mock_llm():
    """Fixture for mocked LLM chain."""
    mock_model = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "### Merged Memory\n\nConsolidated info here."
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    mock_llm_model = AsyncMock()
    mock_llm_model.create_instance = AsyncMock(return_value=mock_model)
    return mock_llm_model, mock_model


class TestUpdateMemory:
    @pytest.mark.asyncio
    async def test_creates_new_memory_when_none_exists(self, mock_agent_data, mock_llm):
        mock_llm_model, mock_model = mock_llm
        mock_agent_data.long_term_memory = None

        with (
            patch(
                "intentkit.core.memory.AgentData.get",
                new_callable=AsyncMock,
                return_value=mock_agent_data,
            ),
            patch(
                "intentkit.core.memory.AgentData.patch",
                new_callable=AsyncMock,
            ) as mock_patch,
            patch(
                "intentkit.models.llm_picker.pick_summarize_model",
                return_value="test-model",
            ),
            patch(
                "intentkit.models.llm.create_llm_model",
                new_callable=AsyncMock,
                return_value=mock_llm_model,
            ),
        ):
            result = await update_memory("agent-1", "User likes cats")

            assert result == "### Merged Memory\n\nConsolidated info here."
            mock_patch.assert_called_once_with("agent-1", {"long_term_memory": result})

            # Verify the LLM was called with only new info (no existing memory)
            call_args = mock_model.ainvoke.call_args[0][0]
            user_msg = call_args[1].content
            assert "### New Information" in user_msg
            assert "### Existing Memory" not in user_msg

    @pytest.mark.asyncio
    async def test_merges_with_existing_memory(self, mock_agent_data, mock_llm):
        mock_llm_model, mock_model = mock_llm
        mock_agent_data.long_term_memory = "### Old Info\n\nUser likes dogs."

        with (
            patch(
                "intentkit.core.memory.AgentData.get",
                new_callable=AsyncMock,
                return_value=mock_agent_data,
            ),
            patch(
                "intentkit.core.memory.AgentData.patch",
                new_callable=AsyncMock,
            ),
            patch(
                "intentkit.models.llm_picker.pick_summarize_model",
                return_value="test-model",
            ),
            patch(
                "intentkit.models.llm.create_llm_model",
                new_callable=AsyncMock,
                return_value=mock_llm_model,
            ),
        ):
            await update_memory("agent-1", "User also likes cats")

            # Verify the LLM was called with both existing and new info
            call_args = mock_model.ainvoke.call_args[0][0]
            user_msg = call_args[1].content
            assert "### Existing Memory" in user_msg
            assert "User likes dogs" in user_msg
            assert "### New Information" in user_msg
            assert "User also likes cats" in user_msg

    @pytest.mark.asyncio
    async def test_truncates_to_max_bytes(self, mock_agent_data, mock_llm):
        mock_llm_model, mock_model = mock_llm
        # Make LLM return something larger than MAX_MEMORY_BYTES
        mock_response = MagicMock()
        mock_response.content = "x" * (MAX_MEMORY_BYTES + 1000)
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with (
            patch(
                "intentkit.core.memory.AgentData.get",
                new_callable=AsyncMock,
                return_value=mock_agent_data,
            ),
            patch(
                "intentkit.core.memory.AgentData.patch",
                new_callable=AsyncMock,
            ) as mock_patch,
            patch(
                "intentkit.models.llm_picker.pick_summarize_model",
                return_value="test-model",
            ),
            patch(
                "intentkit.models.llm.create_llm_model",
                new_callable=AsyncMock,
                return_value=mock_llm_model,
            ),
        ):
            result = await update_memory("agent-1", "new content")

            assert len(result.encode("utf-8")) <= MAX_MEMORY_BYTES
            saved_data = mock_patch.call_args[0][1]
            assert (
                len(saved_data["long_term_memory"].encode("utf-8")) <= MAX_MEMORY_BYTES
            )

    @pytest.mark.asyncio
    async def test_fallback_on_llm_failure(self, mock_agent_data):
        mock_agent_data.long_term_memory = "existing memory"

        mock_llm_model = AsyncMock()
        mock_llm_model.create_instance = AsyncMock(
            side_effect=Exception("LLM unavailable")
        )

        with (
            patch(
                "intentkit.core.memory.AgentData.get",
                new_callable=AsyncMock,
                return_value=mock_agent_data,
            ),
            patch(
                "intentkit.core.memory.AgentData.patch",
                new_callable=AsyncMock,
            ) as mock_patch,
            patch(
                "intentkit.models.llm_picker.pick_summarize_model",
                return_value="test-model",
            ),
            patch(
                "intentkit.models.llm.create_llm_model",
                new_callable=AsyncMock,
                return_value=mock_llm_model,
            ),
        ):
            result = await update_memory("agent-1", "new info")

            # Fallback should concatenate existing + new
            assert "existing memory" in result
            assert "new info" in result
            mock_patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_no_existing_memory_on_llm_failure(self, mock_agent_data):
        mock_agent_data.long_term_memory = None

        mock_llm_model = AsyncMock()
        mock_llm_model.create_instance = AsyncMock(
            side_effect=Exception("LLM unavailable")
        )

        with (
            patch(
                "intentkit.core.memory.AgentData.get",
                new_callable=AsyncMock,
                return_value=mock_agent_data,
            ),
            patch(
                "intentkit.core.memory.AgentData.patch",
                new_callable=AsyncMock,
            ) as mock_patch,
            patch(
                "intentkit.models.llm_picker.pick_summarize_model",
                return_value="test-model",
            ),
            patch(
                "intentkit.models.llm.create_llm_model",
                new_callable=AsyncMock,
                return_value=mock_llm_model,
            ),
        ):
            result = await update_memory("agent-1", "new info")

            assert result == "new info"
            mock_patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_non_string_llm_response(self, mock_agent_data, mock_llm):
        mock_llm_model, mock_model = mock_llm
        # Simulate LLM returning non-string content
        mock_response = MagicMock()
        mock_response.content = ["some", "list"]
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with (
            patch(
                "intentkit.core.memory.AgentData.get",
                new_callable=AsyncMock,
                return_value=mock_agent_data,
            ),
            patch(
                "intentkit.core.memory.AgentData.patch",
                new_callable=AsyncMock,
            ),
            patch(
                "intentkit.models.llm_picker.pick_summarize_model",
                return_value="test-model",
            ),
            patch(
                "intentkit.models.llm.create_llm_model",
                new_callable=AsyncMock,
                return_value=mock_llm_model,
            ),
        ):
            result = await update_memory("agent-1", "new content")
            # Should be converted to string
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_invalidates_lead_cache_for_team_agent(
        self, mock_agent_data, mock_llm
    ):
        """team-* agent IDs should trigger lead cache invalidation."""
        mock_llm_model, _ = mock_llm

        with (
            patch(
                "intentkit.core.memory.AgentData.get",
                new_callable=AsyncMock,
                return_value=mock_agent_data,
            ),
            patch(
                "intentkit.core.memory.AgentData.patch",
                new_callable=AsyncMock,
            ),
            patch(
                "intentkit.models.llm_picker.pick_summarize_model",
                return_value="test-model",
            ),
            patch(
                "intentkit.models.llm.create_llm_model",
                new_callable=AsyncMock,
                return_value=mock_llm_model,
            ),
            patch("intentkit.core.lead.cache.invalidate_lead_cache") as mock_invalidate,
        ):
            await update_memory("team-my-team-id", "new content")

            mock_invalidate.assert_called_once_with("my-team-id")

    @pytest.mark.asyncio
    async def test_does_not_invalidate_lead_cache_for_regular_agent(
        self, mock_agent_data, mock_llm
    ):
        """Regular agent IDs should not trigger lead cache invalidation."""
        mock_llm_model, _ = mock_llm

        with (
            patch(
                "intentkit.core.memory.AgentData.get",
                new_callable=AsyncMock,
                return_value=mock_agent_data,
            ),
            patch(
                "intentkit.core.memory.AgentData.patch",
                new_callable=AsyncMock,
            ),
            patch(
                "intentkit.models.llm_picker.pick_summarize_model",
                return_value="test-model",
            ),
            patch(
                "intentkit.models.llm.create_llm_model",
                new_callable=AsyncMock,
                return_value=mock_llm_model,
            ),
            patch("intentkit.core.lead.cache.invalidate_lead_cache") as mock_invalidate,
        ):
            await update_memory("agent-xyz", "new content")

            mock_invalidate.assert_not_called()
