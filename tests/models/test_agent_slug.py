"""Tests for AgentCore slug field validation."""

import pytest
from pydantic import ValidationError

from intentkit.models.agent.core import AgentCore


class TestAgentCoreSlugValidation:
    """Tests for slug field pattern and length constraints on AgentCore."""

    def test_slug_accepts_valid_lowercase(self):
        agent = AgentCore(name="Test", model="gpt-4o-mini", slug="my-agent")
        assert agent.slug == "my-agent"

    def test_slug_accepts_two_char_minimum(self):
        agent = AgentCore(name="Test", model="gpt-4o-mini", slug="ab")
        assert agent.slug == "ab"

    def test_slug_accepts_numbers_in_middle(self):
        agent = AgentCore(name="Test", model="gpt-4o-mini", slug="agent-42-test")
        assert agent.slug == "agent-42-test"

    def test_slug_accepts_single_letter_start_number_end(self):
        agent = AgentCore(name="Test", model="gpt-4o-mini", slug="a1")
        assert agent.slug == "a1"

    def test_slug_rejects_uppercase(self):
        with pytest.raises(ValidationError, match="pattern"):
            AgentCore(name="Test", model="gpt-4o-mini", slug="My-Agent")

    def test_slug_rejects_starting_with_number(self):
        with pytest.raises(ValidationError, match="pattern"):
            AgentCore(name="Test", model="gpt-4o-mini", slug="1agent")

    def test_slug_rejects_ending_with_hyphen(self):
        with pytest.raises(ValidationError, match="pattern"):
            AgentCore(name="Test", model="gpt-4o-mini", slug="agent-")

    def test_slug_rejects_starting_with_hyphen(self):
        with pytest.raises(ValidationError, match="pattern"):
            AgentCore(name="Test", model="gpt-4o-mini", slug="-agent")

    def test_slug_rejects_single_char(self):
        with pytest.raises(ValidationError, match="string_too_short"):
            AgentCore(name="Test", model="gpt-4o-mini", slug="a")

    def test_slug_rejects_spaces(self):
        with pytest.raises(ValidationError, match="pattern"):
            AgentCore(name="Test", model="gpt-4o-mini", slug="my agent")

    def test_slug_rejects_underscores(self):
        with pytest.raises(ValidationError, match="pattern"):
            AgentCore(name="Test", model="gpt-4o-mini", slug="my_agent")

    def test_slug_rejects_special_chars(self):
        with pytest.raises(ValidationError, match="pattern"):
            AgentCore(name="Test", model="gpt-4o-mini", slug="my.agent")

    def test_slug_allows_none(self):
        agent = AgentCore(name="Test", model="gpt-4o-mini", slug=None)
        assert agent.slug is None

    def test_slug_defaults_to_none(self):
        agent = AgentCore(name="Test", model="gpt-4o-mini")
        assert agent.slug is None

    def test_slug_max_length_60(self):
        long_slug = "a" * 60
        agent = AgentCore(name="Test", model="gpt-4o-mini", slug=long_slug)
        assert agent.slug == long_slug

    def test_slug_rejects_over_60_chars(self):
        with pytest.raises(ValidationError, match="string_too_long"):
            AgentCore(name="Test", model="gpt-4o-mini", slug="a" * 61)


class TestAgentCoreHashExcludesSlug:
    """Tests that slug is excluded from the content hash."""

    def test_hash_same_with_different_slugs(self):
        agent1 = AgentCore(name="Test", model="gpt-4o-mini", slug="slug-one")
        agent2 = AgentCore(name="Test", model="gpt-4o-mini", slug="slug-two")
        assert agent1.hash() == agent2.hash()

    def test_hash_same_with_and_without_slug(self):
        agent1 = AgentCore(name="Test", model="gpt-4o-mini", slug="my-slug")
        agent2 = AgentCore(name="Test", model="gpt-4o-mini", slug=None)
        assert agent1.hash() == agent2.hash()

    def test_hash_differs_with_different_content(self):
        agent1 = AgentCore(name="Test A", model="gpt-4o-mini", slug="same-slug")
        agent2 = AgentCore(name="Test B", model="gpt-4o-mini", slug="same-slug")
        assert agent1.hash() != agent2.hash()
