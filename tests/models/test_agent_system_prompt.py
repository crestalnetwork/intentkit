"""Tests for the merged system_prompt field validation on AgentUpdate."""

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from intentkit.models.agent.user_input import AgentUpdate


class TestSystemPromptValidation:
    def test_accepts_plain_text(self):
        agent = AgentUpdate(
            name="Test", model="gpt-4o-mini", system_prompt="Be helpful."
        )
        assert agent.system_prompt == "Be helpful."

    def test_accepts_level2_and_deeper_headings(self):
        text = "## Purpose\n\nHelp users.\n\n### Details\n\n#### More"
        agent = AgentUpdate(name="Test", model="gpt-4o-mini", system_prompt=text)
        assert agent.system_prompt == text

    def test_rejects_level1_heading(self):
        with pytest.raises(ValidationError, match="Level 1 headings"):
            AgentUpdate(
                name="Test",
                model="gpt-4o-mini",
                system_prompt="# Top Heading\n\nContent",
            )

    def test_rejects_level1_heading_mid_text(self):
        with pytest.raises(ValidationError, match="Level 1 headings"):
            AgentUpdate(
                name="Test",
                model="gpt-4o-mini",
                system_prompt="Intro\n\n# Heading\n\nContent",
            )

    def test_rejects_over_max_length(self):
        with pytest.raises(ValidationError, match="at most 200000"):
            AgentUpdate(name="Test", model="gpt-4o-mini", system_prompt="x" * 200001)

    def test_extra_prompt_still_rejects_level2_headings(self):
        with pytest.raises(ValidationError, match="Level 1 and 2 headings"):
            AgentUpdate(
                name="Test",
                model="gpt-4o-mini",
                extra_prompt="## Not Allowed Here",
            )


class TestSchemaPatternConsistency:
    """The hand-written schema.json pattern must agree with the Pydantic
    validator on representative inputs, so client- and server-side validation
    don't drift."""

    @pytest.fixture(scope="class")
    def schema_pattern(self) -> re.Pattern[str]:
        schema_path = (
            Path(__file__).parents[2] / "intentkit" / "models" / "agent" / "schema.json"
        )
        schema = json.loads(schema_path.read_text())
        return re.compile(schema["properties"]["system_prompt"]["pattern"])

    @pytest.mark.parametrize(
        ("text", "allowed"),
        [
            ("plain text", True),
            ("## Section\n\nbody", True),
            ("### Deep\n\nbody\n\n#### Deeper", True),
            ("#hashtag no space", True),
            ("# Top Heading", False),
            ("intro\n# Mid Heading\nbody", False),
        ],
    )
    def test_pattern_matches_validator(
        self, schema_pattern: re.Pattern[str], text: str, allowed: bool
    ) -> None:
        assert bool(schema_pattern.fullmatch(text)) is allowed

        if allowed:
            agent = AgentUpdate(name="T", model="gpt-4o-mini", system_prompt=text)
            assert agent.system_prompt == text
        else:
            with pytest.raises(ValidationError):
                AgentUpdate(name="T", model="gpt-4o-mini", system_prompt=text)
