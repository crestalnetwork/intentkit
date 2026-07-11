"""Shared constants and helpers for the lead agent system."""

# Defaults for the lead agent — used by engine and get_self_info tool.
LEAD_DEFAULT_NAME = "Team Lead"
LEAD_DEFAULT_PERSONALITY = (
    "Helpful team assistant. Let sub-agents handle technical details."
)

# LLM-facing contract for the merged system_prompt field — used by the
# create/update team agent tool input schemas.
SYSTEM_PROMPT_FIELD_DESCRIPTION = (
    "System prompt defining the agent's purpose, personality, principles, "
    "and behavior. Markdown; use level 2+ headings (##, ###) for sections, "
    "level 1 headings are not allowed."
)


def compose_system_prompt(
    *,
    purpose: str,
    personality: str | None = None,
    principles: str | None = None,
    rules: str | None = None,
) -> str:
    """Render the section scaffold for built-in (in-memory) agents.

    Mirrors the heading vocabulary the data migration used when merging the
    old per-field prompts, so built-in and user agents read alike.
    """
    sections = [f"## Purpose\n\n{purpose}"]
    if personality:
        sections.append(f"## Personality\n\n{personality}")
    if principles:
        sections.append(f"## Principles\n\n{principles}")
    if rules:
        sections.append(f"## Initial Rules\n\n{rules}")
    return "\n\n".join(sections)


def excerpt(text: str | None, limit: int) -> str | None:
    """Collapse whitespace and hard-cap length.

    Used to keep prompt-listing lines short — both to limit context noise and
    to cap any prompt-injection payload carried in untrusted text. Slices the
    input before splitting so huge prompts don't pay a full-string split.
    """
    if not text:
        return None
    return " ".join(text[: limit * 4].split())[:limit]
