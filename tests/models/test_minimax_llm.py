"""Integration tests for MiniMax LLM provider."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from intentkit.models.llm import (
    LLMModel,
    LLMModelInfo,
    LLMProvider,
    MiniMaxLLM,
    create_llm_model,
)


def _make_minimax_model_info(**overrides):
    """Create a MiniMax LLMModelInfo for testing."""
    from datetime import UTC, datetime

    defaults = {
        "id": "MiniMax-M2.7",
        "name": "MiniMax M2.7",
        "provider": LLMProvider.MINIMAX,
        "enabled": True,
        "input_price": Decimal("0.3"),
        "cached_input_price": Decimal("0.03"),
        "output_price": Decimal("1.2"),
        "context_length": 204800,
        "output_length": 131072,
        "intelligence": 5,
        "speed": 3,
        "supports_image_input": False,
        "reasoning_effort": "high",
        "supports_temperature": True,
        "supports_frequency_penalty": True,
        "supports_presence_penalty": True,
        "timeout": 300,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return LLMModelInfo(**defaults)


class TestMiniMaxLLMProvider:
    """Tests for the MiniMax LLM provider enum and configuration."""

    def test_minimax_provider_exists(self):
        assert LLMProvider.MINIMAX == "minimax"

    def test_minimax_display_name(self):
        assert LLMProvider.MINIMAX.display_name() == "MiniMax"

    def test_minimax_configured_with_key(self):
        with patch("intentkit.models.llm.config") as mock_config:
            mock_config.minimax_api_key = "mm-test-key"
            assert LLMProvider.MINIMAX.is_configured is True

    def test_minimax_not_configured_without_key(self):
        with patch("intentkit.models.llm.config") as mock_config:
            mock_config.minimax_api_key = None
            assert LLMProvider.MINIMAX.is_configured is False

    def test_minimax_not_configured_with_empty_key(self):
        with patch("intentkit.models.llm.config") as mock_config:
            mock_config.minimax_api_key = ""
            assert LLMProvider.MINIMAX.is_configured is False


class TestMiniMaxLLMClass:
    """Tests for the MiniMaxLLM class."""

    def test_minimax_llm_is_subclass_of_llm_model(self):
        assert issubclass(MiniMaxLLM, LLMModel)

    @pytest.mark.asyncio
    async def test_create_instance_uses_correct_base_url(self):
        info = _make_minimax_model_info()
        llm = MiniMaxLLM(
            model_name="MiniMax-M2.7",
            temperature=0.7,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            info=info,
        )

        with (
            patch("intentkit.models.llm.config") as mock_config,
            patch.object(
                LLMModelInfo, "get", new_callable=AsyncMock, return_value=info
            ),
        ):
            mock_config.minimax_api_key = "mm-test-key"
            instance = await llm.create_instance()

        assert instance.openai_api_base == "https://api.minimax.io/v1"

    @pytest.mark.asyncio
    async def test_create_instance_uses_api_key(self):
        info = _make_minimax_model_info()
        llm = MiniMaxLLM(
            model_name="MiniMax-M2.7",
            temperature=0.7,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            info=info,
        )

        with (
            patch("intentkit.models.llm.config") as mock_config,
            patch.object(
                LLMModelInfo, "get", new_callable=AsyncMock, return_value=info
            ),
        ):
            mock_config.minimax_api_key = "mm-test-key-123"
            instance = await llm.create_instance()

        assert instance.openai_api_key.get_secret_value() == "mm-test-key-123"

    @pytest.mark.asyncio
    async def test_create_instance_with_temperature(self):
        info = _make_minimax_model_info(supports_temperature=True)
        llm = MiniMaxLLM(
            model_name="MiniMax-M2.7",
            temperature=0.5,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            info=info,
        )

        with (
            patch("intentkit.models.llm.config") as mock_config,
            patch.object(
                LLMModelInfo, "get", new_callable=AsyncMock, return_value=info
            ),
        ):
            mock_config.minimax_api_key = "mm-test-key"
            instance = await llm.create_instance()

        assert instance.temperature == 0.5

    @pytest.mark.asyncio
    async def test_create_instance_without_temperature_support(self):
        info = _make_minimax_model_info(supports_temperature=False)
        llm = MiniMaxLLM(
            model_name="MiniMax-M2.7",
            temperature=0.9,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            info=info,
        )

        with (
            patch("intentkit.models.llm.config") as mock_config,
            patch.object(
                LLMModelInfo, "get", new_callable=AsyncMock, return_value=info
            ),
        ):
            mock_config.minimax_api_key = "mm-test-key"
            instance = await llm.create_instance()

        # Temperature should not be 0.9 since model doesn't support it
        assert instance.temperature != 0.9

    @pytest.mark.asyncio
    async def test_create_instance_highspeed_model(self):
        info = _make_minimax_model_info(
            id="MiniMax-M2.7-highspeed",
            name="MiniMax M2.7 Highspeed",
            intelligence=4,
            speed=5,
            reasoning_effort=None,
        )
        llm = MiniMaxLLM(
            model_name="MiniMax-M2.7-highspeed",
            temperature=0.7,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            info=info,
        )

        with (
            patch("intentkit.models.llm.config") as mock_config,
            patch.object(
                LLMModelInfo, "get", new_callable=AsyncMock, return_value=info
            ),
        ):
            mock_config.minimax_api_key = "mm-test-key"
            instance = await llm.create_instance()

        assert instance.model_name == "MiniMax-M2.7-highspeed"

    @pytest.mark.asyncio
    async def test_create_instance_params_override(self):
        info = _make_minimax_model_info()
        llm = MiniMaxLLM(
            model_name="MiniMax-M2.7",
            temperature=0.7,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            info=info,
        )

        with (
            patch("intentkit.models.llm.config") as mock_config,
            patch.object(
                LLMModelInfo, "get", new_callable=AsyncMock, return_value=info
            ),
        ):
            mock_config.minimax_api_key = "mm-test-key"
            instance = await llm.create_instance({"max_retries": 5})

        assert instance.max_retries == 5


class TestMiniMaxFactory:
    """Tests for MiniMax integration with the LLM factory."""

    @pytest.mark.asyncio
    async def test_create_llm_model_returns_minimax(self):
        info = _make_minimax_model_info()

        with patch.object(LLMModelInfo, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = info
            model = await create_llm_model("MiniMax-M2.7")

        assert isinstance(model, MiniMaxLLM)
        assert model.model_name == "MiniMax-M2.7"

    @pytest.mark.asyncio
    async def test_create_llm_model_minimax_with_custom_params(self):
        info = _make_minimax_model_info()

        with patch.object(LLMModelInfo, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = info
            model = await create_llm_model(
                "MiniMax-M2.7",
                temperature=0.3,
                frequency_penalty=0.1,
                presence_penalty=0.2,
            )

        assert isinstance(model, MiniMaxLLM)
        assert model.temperature == 0.3
        assert model.frequency_penalty == 0.1
        assert model.presence_penalty == 0.2


class TestMiniMaxModelInfo:
    """Tests for MiniMax model information."""

    def test_minimax_m27_model_info(self):
        info = _make_minimax_model_info()
        assert info.provider == LLMProvider.MINIMAX
        assert info.intelligence == 5
        assert info.context_length == 204800
        assert info.output_length == 131072
        assert info.input_price == Decimal("0.3")
        assert info.output_price == Decimal("1.2")

    def test_minimax_m27_highspeed_model_info(self):
        info = _make_minimax_model_info(
            id="MiniMax-M2.7-highspeed",
            name="MiniMax M2.7 Highspeed",
            intelligence=4,
            speed=5,
            input_price=Decimal("0.07"),
            cached_input_price=None,
            output_price=Decimal("0.28"),
            reasoning_effort=None,
            timeout=180,
        )
        assert info.provider == LLMProvider.MINIMAX
        assert info.speed == 5
        assert info.intelligence == 4
        assert info.input_price == Decimal("0.07")
