"""Validate the predefined agent definitions that actually ship.

The sync's own tests mock ``PUBLIC_AGENTS_DIR``, so before this file nothing
checked the real definitions: a typo or a field removed from the model surfaced
only at production startup, where the loader logs the failure and skips the
agent. That is how ``temperature:`` sat in these files long after the field was
removed.
"""

from pathlib import Path

import pytest
import yaml as pyyaml

import intentkit.models.llm as llm_module
from intentkit.core.public_agents import (
    PUBLIC_AGENTS_DIR,
    parse_agent_markdown,
)
from intentkit.models.agent.user_input import AgentUpdate

AGENT_FILES = sorted(PUBLIC_AGENTS_DIR.rglob("*.md"))
LIVE_MODEL_IDS = {
    row["id"]
    for row in pyyaml.safe_load(
        Path(llm_module.__file__).with_name("llm.yaml").read_text(encoding="utf-8")
    )
}


def test_definitions_are_present():
    """A refactor that silently stops finding them must fail here."""
    assert AGENT_FILES, f"no agent definitions under {PUBLIC_AGENTS_DIR}"


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_definition_parses_and_validates(path):
    """Every shipped definition must survive the exact load the sync performs."""
    data = parse_agent_markdown(path.read_text(), source=path.name)
    agent = AgentUpdate.model_validate(data)

    assert agent.name, f"{path.name}: name is required"
    assert data.get("slug") == path.stem, (
        f"{path.name}: slug must match the filename so the sync's archive pass "
        "keys on a stable value"
    )
    assert agent.description, f"{path.name}: description is shown in listings"
    assert agent.system_prompt, f"{path.name}: body is empty"
    # legacy_ids routing would keep a retired id working, but every sync
    # would then re-mint the agent with it; pin definitions to live ids.
    assert agent.model in LIVE_MODEL_IDS, (
        f"{path.name}: model {agent.model!r} is not a live catalog id"
    )


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_definition_is_usable_as_a_sub_agent(path):
    """Sub-agent runs are non-interactive: AgentContext.is_interactive is False,
    and ui_ask_user is dropped from the toolset. A prompt that waits for an
    answer would hang the delegating agent."""
    body = parse_agent_markdown(path.read_text(), source=path.name)["system_prompt"]
    lowered = body.lower()

    for phrase in ("ask clarifying question", "ask the user what", "ask me what"):
        assert phrase not in lowered, (
            f"{path.name}: instructs the agent to ask the caller a question, "
            "which a sub-agent run cannot do"
        )


def test_slugs_are_unique():
    """Two definitions sharing a slug would silently overwrite each other."""
    slugs = [p.stem for p in AGENT_FILES]
    duplicates = {s for s in slugs if slugs.count(s) > 1}
    assert not duplicates, f"duplicate slugs: {sorted(duplicates)}"


class TestFrontmatterParsing:
    """The parser is strict on purpose -- AgentUpdate silently drops extras."""

    BODY = "---\nname: T\nslug: t\n---\n\n## Purpose\n\nDo the thing.\n"

    def test_splits_frontmatter_from_body(self):
        data = parse_agent_markdown(self.BODY, source="t.md")
        assert data["name"] == "T"
        assert data["system_prompt"] == "## Purpose\n\nDo the thing."

    def test_rejects_unknown_keys(self):
        text = self.BODY.replace("slug: t", "slug: t\ntemperature: 0.7")
        with pytest.raises(ValueError, match="unknown frontmatter keys: temperature"):
            parse_agent_markdown(text, source="t.md")

    def test_rejects_a_misspelled_key(self):
        """The failure this replaces: `slugg:` fell back to the filename."""
        text = self.BODY.replace("slug: t", "slugg: t")
        with pytest.raises(ValueError, match="slugg"):
            parse_agent_markdown(text, source="t.md")

    def test_allows_tags_which_is_not_an_agent_field(self):
        text = self.BODY.replace("slug: t", "slug: t\ntags:\n- Base")
        assert parse_agent_markdown(text, source="t.md")["tags"] == ["Base"]

    def test_rejects_system_prompt_in_frontmatter(self):
        text = self.BODY.replace("slug: t", "slug: t\nsystem_prompt: sneaky")
        with pytest.raises(ValueError, match="comes from the document body"):
            parse_agent_markdown(text, source="t.md")

    def test_rejects_a_missing_frontmatter_block(self):
        with pytest.raises(ValueError, match="must start with"):
            parse_agent_markdown("## Purpose\n\nNo frontmatter.\n", source="t.md")

    def test_rejects_an_unclosed_frontmatter_block(self):
        with pytest.raises(ValueError, match="never closed"):
            parse_agent_markdown("---\nname: T\n\n## Purpose\n", source="t.md")

    def test_rejects_an_empty_body(self):
        with pytest.raises(ValueError, match="body .* is empty"):
            parse_agent_markdown("---\nname: T\n---\n\n   \n", source="t.md")

    def test_keeps_horizontal_rules_in_the_body(self):
        """A `---` inside the prompt must not be mistaken for a delimiter."""
        text = "---\nname: T\n---\n\nBefore\n\n---\n\nAfter\n"
        body = parse_agent_markdown(text, source="t.md")["system_prompt"]
        assert body == "Before\n\n---\n\nAfter"
