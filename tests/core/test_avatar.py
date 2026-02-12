from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.avatar import (
    _build_agent_profile,
    _generate_image_google,
    _generate_image_openai,
    _generate_image_openrouter,
    _generate_image_xai,
    generate_avatar,
    select_model_and_generate,
)


@pytest.fixture
def mock_config():
    with patch("intentkit.core.avatar.config") as mock:
        mock.openrouter_api_key = None
        mock.google_api_key = None
        mock.openai_api_key = None
        mock.xai_api_key = None
        mock.env = "test"
        mock.aws_s3_cdn_url = "https://cdn.example.com"
        yield mock


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.id = "test-agent-123"
    agent.name = "Test Agent"
    agent.description = "A helpful test agent"
    agent.purpose = "Testing avatar generation"
    agent.personality = "Friendly and precise"
    agent.principles = "Always be accurate"
    agent.prompt = "You are a test agent."
    agent.prompt_append = None
    agent.extra_prompt = None
    return agent


class TestBuildAgentProfile:
    def test_builds_profile_from_all_fields(self, mock_agent):
        profile = _build_agent_profile("test-agent-123", mock_agent)
        assert "### Name" in profile
        assert "Test Agent" in profile
        assert "### Description" in profile
        assert "### Purpose" in profile
        assert "### Personality" in profile
        assert "### Principles" in profile
        assert "### System Prompt" in profile

    def test_skips_none_fields(self, mock_agent):
        mock_agent.purpose = None
        mock_agent.personality = None
        mock_agent.principles = None
        mock_agent.prompt = None
        profile = _build_agent_profile("test-agent-123", mock_agent)
        assert "### Purpose" not in profile
        assert "### Personality" not in profile
        assert "### Name" in profile

    def test_skips_empty_string_fields(self, mock_agent):
        mock_agent.purpose = "   "
        profile = _build_agent_profile("test-agent-123", mock_agent)
        assert "### Purpose" not in profile

    def test_fallback_to_agent_id(self):
        agent = MagicMock()
        agent.name = None
        agent.description = None
        agent.purpose = None
        agent.personality = None
        agent.principles = None
        agent.prompt = None
        agent.prompt_append = None
        agent.extra_prompt = None
        profile = _build_agent_profile("fallback-id", agent)
        assert "fallback-id" in profile

    def test_handles_missing_attributes(self):
        """Agent-like objects that don't have all fields (e.g. AgentUpdate)."""

        class MinimalAgent:
            name = "Minimal"

        agent = MinimalAgent()
        profile = _build_agent_profile("minimal-id", agent)
        assert "### Name" in profile
        assert "Minimal" in profile


class TestSelectModelAndGenerate:
    @pytest.mark.asyncio
    async def test_tries_openrouter_first(self, mock_config):
        mock_config.openrouter_api_key = "or-key"
        fake_bytes = b"fake-image-data"

        with patch(
            "intentkit.core.avatar._generate_image_openrouter",
            new_callable=AsyncMock,
            return_value=fake_bytes,
        ) as mock_or:
            result = await select_model_and_generate("test prompt")
            assert result == fake_bytes
            mock_or.assert_called_once_with("test prompt")

    @pytest.mark.asyncio
    async def test_falls_through_to_google(self, mock_config):
        mock_config.openrouter_api_key = None
        mock_config.google_api_key = "google-key"
        fake_bytes = b"google-image"

        with patch(
            "intentkit.core.avatar._generate_image_google",
            new_callable=AsyncMock,
            return_value=fake_bytes,
        ) as mock_google:
            result = await select_model_and_generate("test prompt")
            assert result == fake_bytes
            mock_google.assert_called_once_with("test prompt")

    @pytest.mark.asyncio
    async def test_falls_through_to_openai(self, mock_config):
        mock_config.openrouter_api_key = None
        mock_config.google_api_key = None
        mock_config.openai_api_key = "openai-key"
        fake_bytes = b"openai-image"

        with patch(
            "intentkit.core.avatar._generate_image_openai",
            new_callable=AsyncMock,
            return_value=fake_bytes,
        ) as mock_openai:
            result = await select_model_and_generate("test prompt")
            assert result == fake_bytes
            mock_openai.assert_called_once_with("test prompt")

    @pytest.mark.asyncio
    async def test_falls_through_to_xai(self, mock_config):
        mock_config.openrouter_api_key = None
        mock_config.google_api_key = None
        mock_config.openai_api_key = None
        mock_config.xai_api_key = "xai-key"
        fake_bytes = b"xai-image"

        with patch(
            "intentkit.core.avatar._generate_image_xai",
            new_callable=AsyncMock,
            return_value=fake_bytes,
        ) as mock_xai:
            result = await select_model_and_generate("test prompt")
            assert result == fake_bytes
            mock_xai.assert_called_once_with("test prompt")

    @pytest.mark.asyncio
    async def test_returns_none_when_no_keys(self, mock_config):
        result = await select_model_and_generate("test prompt")
        assert result is None

    @pytest.mark.asyncio
    async def test_falls_through_on_failure(self, mock_config):
        mock_config.openrouter_api_key = "or-key"
        mock_config.google_api_key = "google-key"
        fake_bytes = b"google-image"

        with (
            patch(
                "intentkit.core.avatar._generate_image_openrouter",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "intentkit.core.avatar._generate_image_google",
                new_callable=AsyncMock,
                return_value=fake_bytes,
            ),
        ):
            result = await select_model_and_generate("test prompt")
            assert result == fake_bytes


class TestGenerateAvatar:
    @pytest.mark.asyncio
    async def test_generate_avatar_success(self, mock_config, mock_agent):
        mock_config.openrouter_api_key = "or-key"
        mock_config.aws_s3_cdn_url = "https://cdn.example.com"

        fake_image = b"png-image-bytes"

        with (
            patch(
                "intentkit.core.avatar._generate_image_prompt",
                new_callable=AsyncMock,
                return_value="a cool avatar prompt",
            ),
            patch(
                "intentkit.core.avatar.select_model_and_generate",
                new_callable=AsyncMock,
                return_value=fake_image,
            ),
            patch(
                "intentkit.core.avatar.store_image_bytes",
                new_callable=AsyncMock,
                return_value="https://cdn.example.com/test/intentkit/avatars/test-agent-123/abc.png",
            ) as mock_store,
        ):
            path = await generate_avatar("test-agent-123", mock_agent)

            mock_store.assert_called_once()
            call_args = mock_store.call_args
            assert call_args[0][0] == fake_image
            assert "avatars/test-agent-123/" in call_args[0][1]
            assert call_args[1]["content_type"] == "image/png"

            assert path == "test/intentkit/avatars/test-agent-123/abc.png"

    @pytest.mark.asyncio
    async def test_generate_avatar_returns_none_on_image_failure(
        self, mock_config, mock_agent
    ):
        with (
            patch(
                "intentkit.core.avatar._generate_image_prompt",
                new_callable=AsyncMock,
                return_value="a prompt",
            ),
            patch(
                "intentkit.core.avatar.select_model_and_generate",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            path = await generate_avatar("test-agent-123", mock_agent)
            assert path is None

    @pytest.mark.asyncio
    async def test_generate_avatar_returns_none_on_s3_failure(
        self, mock_config, mock_agent
    ):
        mock_config.openrouter_api_key = "or-key"

        with (
            patch(
                "intentkit.core.avatar._generate_image_prompt",
                new_callable=AsyncMock,
                return_value="a prompt",
            ),
            patch(
                "intentkit.core.avatar.select_model_and_generate",
                new_callable=AsyncMock,
                return_value=b"image-bytes",
            ),
            patch(
                "intentkit.core.avatar.store_image_bytes",
                new_callable=AsyncMock,
                side_effect=Exception("S3 is down"),
            ),
        ):
            path = await generate_avatar("test-agent-123", mock_agent)
            assert path is None


class TestProviderFunctions:
    @pytest.mark.asyncio
    async def test_openrouter_with_b64_response(self):
        import base64

        fake_b64 = base64.b64encode(b"image-data").decode()
        mock_data = MagicMock()
        mock_data.b64_json = fake_b64
        mock_data.url = None

        mock_response = MagicMock()
        mock_response.data = [mock_data]

        with patch("intentkit.core.avatar.config") as mock_config:
            mock_config.openrouter_api_key = "test-key"
            with patch("intentkit.core.avatar.AsyncOpenAI") as mock_openai_cls:
                mock_client = AsyncMock()
                mock_openai_cls.return_value = mock_client
                mock_client.images.generate.return_value = mock_response

                result = await _generate_image_openrouter("test prompt")

                assert result == b"image-data"
                mock_openai_cls.assert_called_once_with(
                    api_key="test-key",
                    base_url="https://openrouter.ai/api/v1",
                )
                mock_client.images.generate.assert_called_once_with(
                    model="bytedance-seed/seedream-4.5",
                    prompt="test prompt",
                    size="1024x1024",
                    n=1,
                )

    @pytest.mark.asyncio
    async def test_openrouter_with_url_response(self):
        mock_data = MagicMock()
        mock_data.b64_json = None
        mock_data.url = "https://example.com/image.png"

        mock_response = MagicMock()
        mock_response.data = [mock_data]

        with patch("intentkit.core.avatar.config") as mock_config:
            mock_config.openrouter_api_key = "test-key"
            with (
                patch("intentkit.core.avatar.AsyncOpenAI") as mock_openai_cls,
                patch(
                    "intentkit.core.avatar._download_image",
                    new_callable=AsyncMock,
                    return_value=b"downloaded-image",
                ) as mock_download,
            ):
                mock_client = AsyncMock()
                mock_openai_cls.return_value = mock_client
                mock_client.images.generate.return_value = mock_response

                result = await _generate_image_openrouter("test prompt")
                assert result == b"downloaded-image"
                mock_download.assert_called_once_with("https://example.com/image.png")

    @pytest.mark.asyncio
    async def test_openrouter_returns_none_on_error(self):
        with patch("intentkit.core.avatar.config") as mock_config:
            mock_config.openrouter_api_key = "test-key"
            with patch("intentkit.core.avatar.AsyncOpenAI") as mock_openai_cls:
                mock_client = AsyncMock()
                mock_openai_cls.return_value = mock_client
                mock_client.images.generate.side_effect = Exception("API error")

                result = await _generate_image_openrouter("test prompt")
                assert result is None

    @pytest.mark.asyncio
    async def test_google_extracts_inline_data(self):
        mock_part = MagicMock()
        mock_part.inline_data.mime_type = "image/png"
        mock_part.inline_data.data = b"google-image-bytes"

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        with patch("intentkit.core.avatar.config") as mock_config:
            mock_config.google_api_key = "google-key"
            with patch("intentkit.core.avatar.genai") as mock_genai:
                mock_client = MagicMock()
                mock_genai.Client.return_value = mock_client
                mock_client.aio.models.generate_content = AsyncMock(
                    return_value=mock_response
                )

                result = await _generate_image_google("test prompt")
                assert result == b"google-image-bytes"

    @pytest.mark.asyncio
    async def test_google_returns_none_on_no_image(self):
        mock_part = MagicMock()
        mock_part.inline_data = None

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        with patch("intentkit.core.avatar.config") as mock_config:
            mock_config.google_api_key = "google-key"
            with patch("intentkit.core.avatar.genai") as mock_genai:
                mock_client = MagicMock()
                mock_genai.Client.return_value = mock_client
                mock_client.aio.models.generate_content = AsyncMock(
                    return_value=mock_response
                )

                result = await _generate_image_google("test prompt")
                assert result is None

    @pytest.mark.asyncio
    async def test_openai_with_b64_response(self):
        import base64

        fake_b64 = base64.b64encode(b"openai-image").decode()
        mock_data = MagicMock()
        mock_data.b64_json = fake_b64
        mock_data.url = None

        mock_response = MagicMock()
        mock_response.data = [mock_data]

        with patch("intentkit.core.avatar.config") as mock_config:
            mock_config.openai_api_key = "openai-key"
            with patch("intentkit.core.avatar.AsyncOpenAI") as mock_openai_cls:
                mock_client = AsyncMock()
                mock_openai_cls.return_value = mock_client
                mock_client.images.generate.return_value = mock_response

                result = await _generate_image_openai("test prompt")
                assert result == b"openai-image"
                mock_openai_cls.assert_called_once_with(api_key="openai-key")
                call_kwargs = mock_client.images.generate.call_args[1]
                assert call_kwargs["model"] == "gpt-image-1-mini"
                assert call_kwargs["size"] == "1024x1024"
                assert call_kwargs["quality"] == "low"

    @pytest.mark.asyncio
    async def test_xai_with_b64_response(self):
        import base64

        fake_b64 = base64.b64encode(b"xai-image").decode()
        mock_data = MagicMock()
        mock_data.b64_json = fake_b64
        mock_data.url = None

        mock_response = MagicMock()
        mock_response.data = [mock_data]

        with patch("intentkit.core.avatar.config") as mock_config:
            mock_config.xai_api_key = "xai-key"
            with patch("intentkit.core.avatar.AsyncOpenAI") as mock_openai_cls:
                mock_client = AsyncMock()
                mock_openai_cls.return_value = mock_client
                mock_client.images.generate.return_value = mock_response

                result = await _generate_image_xai("test prompt")
                assert result == b"xai-image"
                mock_openai_cls.assert_called_once_with(
                    api_key="xai-key",
                    base_url="https://api.x.ai/v1",
                )
