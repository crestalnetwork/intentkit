"""Tests for the team publish-agent endpoint."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from intentkit.models.agent import (
    AgentExample,
    AgentPublicInfo,
    AgentPublishInput,
    AgentTag,
)


def _example(name: str = "Hello") -> AgentExample:
    return AgentExample(name=name, description="desc", prompt="prompt")


class TestAgentPublishInput:
    """Validation rules on the team publish request body."""

    def test_minimal_valid_payload(self) -> None:
        body = AgentPublishInput.model_validate(
            {
                "description": "An assistant",
                "example_intro": "Try one of these:",
                "examples": [
                    {"name": "n", "description": "d", "prompt": "p"},
                ],
            }
        )
        assert body.tags is None
        assert len(body.examples) == 1

    def test_tags_with_enum_values(self) -> None:
        body = AgentPublishInput(
            description="A",
            example_intro="B",
            examples=[_example()],
            tags=[AgentTag.MUSIC, AgentTag.MOVIES],
        )
        assert [t.value for t in body.tags or []] == ["music", "movies"]

    def test_rejects_more_than_three_tags(self) -> None:
        with pytest.raises(ValidationError):
            AgentPublishInput(
                description="A",
                example_intro="B",
                examples=[_example()],
                tags=[
                    AgentTag.MUSIC,
                    AgentTag.MOVIES,
                    AgentTag.GAMES,
                    AgentTag.BOOKS,
                ],
            )

    def test_rejects_unknown_tag(self) -> None:
        with pytest.raises(ValidationError):
            AgentPublishInput.model_validate(
                {
                    "description": "A",
                    "example_intro": "B",
                    "examples": [{"name": "n", "description": "d", "prompt": "p"}],
                    "tags": ["not-a-real-tag"],
                }
            )

    def test_rejects_empty_examples(self) -> None:
        with pytest.raises(ValidationError):
            AgentPublishInput(
                description="A",
                example_intro="B",
                examples=[],
                tags=None,
            )

    def test_rejects_too_many_examples(self) -> None:
        with pytest.raises(ValidationError):
            AgentPublishInput(
                description="A",
                example_intro="B",
                examples=[_example(str(i)) for i in range(7)],
                tags=None,
            )

    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            AgentPublishInput.model_validate(
                {
                    "example_intro": "B",
                    "examples": [{"name": "n", "description": "d", "prompt": "p"}],
                }
            )

    def test_rejects_extra_fields(self) -> None:
        # Frontend must not be able to sneak in fee_percentage / ticker / etc.
        with pytest.raises(ValidationError):
            AgentPublishInput.model_validate(
                {
                    "description": "A",
                    "example_intro": "B",
                    "examples": [{"name": "n", "description": "d", "prompt": "p"}],
                    "fee_percentage": 0,
                }
            )


class TestPublishAgentEndpoint:
    """Handler-level checks: fee override, field passthrough."""

    @pytest.mark.asyncio
    @patch("app.team.agent.AgentResponse.from_agent", new_callable=AsyncMock)
    @patch("app.team.agent.AgentData.get", new_callable=AsyncMock)
    @patch("app.team.agent.publish_agent", new_callable=AsyncMock)
    @patch("app.team.agent.get_team_agent", new_callable=AsyncMock)
    async def test_forces_fee_percentage_to_one_and_passes_through_fields(
        self,
        mock_get_team_agent: AsyncMock,
        mock_publish_agent: AsyncMock,
        mock_agent_data_get: AsyncMock,
        mock_from_agent: AsyncMock,
    ) -> None:
        from app.team.agent import publish_agent_endpoint

        agent = MagicMock()
        agent.id = "agent-1"
        mock_get_team_agent.return_value = agent

        latest = MagicMock()
        latest.id = "agent-1"
        mock_publish_agent.return_value = latest
        mock_agent_data_get.return_value = MagicMock()

        response = MagicMock()
        response.model_dump_json.return_value = "{}"
        response.etag.return_value = "abc"
        mock_from_agent.return_value = response

        body = AgentPublishInput(
            description="A public description",
            example_intro="Try these prompts:",
            examples=[_example("Greet")],
            tags=[AgentTag.MUSIC],
        )

        await publish_agent_endpoint(
            agent_id="agent-1", body=body, auth=("user-1", "team-1")
        )

        assert mock_publish_agent.await_count == 1
        assert mock_publish_agent.await_args is not None
        kwargs = mock_publish_agent.await_args.kwargs
        assert kwargs["agent_id"] == "agent-1"
        # description is a core agent field now, passed alongside public info.
        assert kwargs["description"] == "A public description"
        public_info: AgentPublicInfo = kwargs["public_info"]
        assert public_info.example_intro == "Try these prompts:"
        assert public_info.examples == [_example("Greet")]
        assert public_info.tags == ["music"]
        assert public_info.fee_percentage == Decimal("1")
        # Fields outside the publish-input contract must remain unset so
        # existing values on the agent are preserved by apply_public_info_update.
        dumped = public_info.model_dump(exclude_unset=False, exclude_none=False)
        for skipped in (
            "ticker",
            "token_address",
            "token_pool",
            "external_website",
            "x402_price",
            "public_extra",
        ):
            assert skipped in dumped
            assert skipped not in public_info.model_fields_set

    @pytest.mark.asyncio
    @patch("app.team.agent.AgentResponse.from_agent", new_callable=AsyncMock)
    @patch("app.team.agent.AgentData.get", new_callable=AsyncMock)
    @patch("app.team.agent.publish_agent", new_callable=AsyncMock)
    @patch("app.team.agent.get_team_agent", new_callable=AsyncMock)
    async def test_omits_tags_when_none(
        self,
        mock_get_team_agent: AsyncMock,
        mock_publish_agent: AsyncMock,
        mock_agent_data_get: AsyncMock,
        mock_from_agent: AsyncMock,
    ) -> None:
        from app.team.agent import publish_agent_endpoint

        mock_get_team_agent.return_value = MagicMock(id="agent-1")
        mock_publish_agent.return_value = MagicMock(id="agent-1")
        mock_agent_data_get.return_value = MagicMock()
        response = MagicMock()
        response.model_dump_json.return_value = "{}"
        response.etag.return_value = "abc"
        mock_from_agent.return_value = response

        body = AgentPublishInput(
            description="d",
            example_intro="i",
            examples=[_example()],
            tags=None,
        )

        await publish_agent_endpoint(
            agent_id="agent-1", body=body, auth=("user-1", "team-1")
        )

        assert mock_publish_agent.await_args is not None
        public_info: AgentPublicInfo = mock_publish_agent.await_args.kwargs[
            "public_info"
        ]
        assert public_info.tags is None
        assert public_info.fee_percentage == Decimal("1")


class TestTagListing:
    """The flat tag list returned by the schema endpoint should be unique
    and cover every value in the enum."""

    def test_listing_covers_enum_and_is_unique(self) -> None:
        from intentkit.models.agent import AGENT_TAG_CATEGORIES

        listed_values = [
            tag.value for tags in AGENT_TAG_CATEGORIES.values() for tag in tags
        ]
        # Every enum value appears exactly once in the listing.
        assert len(listed_values) == len(set(listed_values))
        assert set(listed_values) == {t.value for t in AgentTag}
