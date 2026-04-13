# Skill Validation & Listing Enhancement

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure the lead agent's agent-manager can correctly create agents with valid skills by enhancing the skill listing, adding backend validation on create, and auto-cleaning stale skills on update.

**Architecture:** Add a shared `get_valid_skills_registry()` utility that loads all skill schemas once and returns a dict of `{category: {skill_name: description}}`. Use it in three places: (1) enhanced listing output, (2) strict validation on agent create, (3) silent cleanup on agent update/override/patch.

**Tech Stack:** Python, SQLAlchemy, Pydantic, pytest

---

### Task 1: Add `get_valid_skills_registry()` utility

**Files:**
- Modify: `intentkit/core/manager/service.py`

**Step 1: Write the failing test**

Create a unit test that calls the new function and verifies it returns a nested dict with known skill categories.

```python
# tests/core/test_skill_registry.py
from intentkit.core.manager.service import get_valid_skills_registry


def test_get_valid_skills_registry_returns_categories():
    """Registry must return a dict keyed by category with skill dicts inside."""
    registry = get_valid_skills_registry()
    assert isinstance(registry, dict)
    # ui category must exist with known skills
    assert "ui" in registry
    assert "ui_show_card" in registry["ui"]
    assert "ui_ask_user" in registry["ui"]
    # each value is a description string
    assert isinstance(registry["ui"]["ui_show_card"], str)
    assert len(registry["ui"]["ui_show_card"]) > 0


def test_get_valid_skills_registry_has_no_empty_categories():
    """Every category must have at least one skill."""
    registry = get_valid_skills_registry()
    for category, skills in registry.items():
        assert len(skills) > 0, f"Category '{category}' has no skills"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_skill_registry.py -v`
Expected: ImportError — `get_valid_skills_registry` does not exist yet.

**Step 3: Implement `get_valid_skills_registry()`**

Add to `intentkit/core/manager/service.py` after the existing `_load_skill_schema` function:

```python
def get_valid_skills_registry() -> dict[str, dict[str, str]]:
    """Return a registry of all valid skill categories and their skills.

    Returns:
        Dict mapping category name -> {skill_name: description}
    """
    registry: dict[str, dict[str, str]] = {}
    try:
        traversable = resources.files("intentkit.skills")
        with resources.as_file(traversable) as skills_root:
            for entry in skills_root.iterdir():
                if not entry.is_dir():
                    continue
                schema_path = entry / "schema.json"
                if not schema_path.is_file():
                    continue
                try:
                    skill_schema = _load_skill_schema(schema_path)
                    states = skill_schema.get("properties", {}).get("states", {}).get("properties", {})
                    if states:
                        category_skills: dict[str, str] = {}
                        for skill_name, skill_def in states.items():
                            desc = skill_def.get("description", "") if isinstance(skill_def, dict) else ""
                            category_skills[skill_name] = desc
                        registry[entry.name] = category_skills
                except (OSError, ValueError, json.JSONDecodeError, jsonref.JsonRefError):
                    continue
    except (AttributeError, ModuleNotFoundError, ImportError):
        pass
    return registry
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_skill_registry.py -v`
Expected: PASS

**Step 5: Run lint**

Run: `ruff format intentkit/core/manager/service.py tests/core/test_skill_registry.py && ruff check --fix intentkit/core/manager/service.py tests/core/test_skill_registry.py`

---

### Task 2: Enhance `get_skills_hierarchical_text()` to include individual skills

**Files:**
- Modify: `intentkit/core/manager/service.py` (function `get_skills_hierarchical_text`)

**Step 1: Write the failing test**

```python
# tests/core/test_skill_listing.py
from intentkit.core.manager.service import get_skills_hierarchical_text


def test_hierarchical_text_includes_individual_skills():
    """Listing must include individual skill names under each category."""
    text = get_skills_hierarchical_text()
    # Must contain individual skill names with backtick formatting
    assert "`ui_show_card`" in text
    assert "`ui_ask_user`" in text


def test_hierarchical_text_includes_skill_descriptions():
    """Each individual skill must have its description shown."""
    text = get_skills_hierarchical_text()
    # ui_show_card description mentions "rich card"
    assert "rich card" in text.lower() or "card" in text.lower()


def test_hierarchical_text_shows_category_then_skills():
    """Category line comes before its individual skills."""
    text = get_skills_hierarchical_text()
    lines = text.split("\n")
    # Find the ui category line and ensure skill lines follow
    ui_category_idx = None
    ui_skill_idx = None
    for i, line in enumerate(lines):
        if "**ui**" in line:
            ui_category_idx = i
        if "`ui_show_card`" in line and ui_category_idx is not None:
            ui_skill_idx = i
            break
    assert ui_category_idx is not None, "ui category not found"
    assert ui_skill_idx is not None, "ui_show_card not found after ui category"
    assert ui_skill_idx > ui_category_idx
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_skill_listing.py -v`
Expected: FAIL — current output doesn't include backtick-formatted individual skill names.

**Step 3: Update `get_skills_hierarchical_text()`**

Replace the skill schema loading and text building loop in `get_skills_hierarchical_text()`. The key change is reading `states.properties` from each schema and appending individual skill lines:

```python
def get_skills_hierarchical_text() -> str:
    """Extract skills organized by category and return as hierarchical text."""
    try:
        traversable = resources.files("intentkit.skills")
        with resources.as_file(traversable) as skills_root:
            categories: dict[str, list[Any]] = {}
            for entry in skills_root.iterdir():
                if not entry.is_dir():
                    continue

                schema_path = entry / "schema.json"
                if not schema_path.is_file():
                    continue

                try:
                    skill_schema = _load_skill_schema(schema_path)
                    skill_name = entry.name
                    skill_title = skill_schema.get(
                        "title", skill_name.replace("_", " ").title()
                    )
                    skill_description = skill_schema.get(
                        "description", "No description available"
                    )
                    skill_tags = cast(list[str], skill_schema.get("x-tags", ["Other"]))

                    # Extract individual skills from states
                    states_props = (
                        skill_schema.get("properties", {})
                        .get("states", {})
                        .get("properties", {})
                    )
                    individual_skills: list[dict[str, str]] = []
                    for ind_name, ind_def in states_props.items():
                        ind_desc = ""
                        if isinstance(ind_def, dict):
                            ind_desc = ind_def.get("description", "")
                        individual_skills.append(
                            {"name": ind_name, "description": ind_desc}
                        )

                    primary_category = skill_tags[0] if skill_tags else "Other"

                    if primary_category not in categories:
                        categories[primary_category] = []

                    categories[primary_category].append(
                        {
                            "name": skill_name,
                            "title": skill_title,
                            "description": skill_description,
                            "individual_skills": individual_skills,
                        }
                    )

                except (
                    OSError,
                    ValueError,
                    json.JSONDecodeError,
                    jsonref.JsonRefError,
                ) as exc:
                    logger.warning(
                        "Failed to load schema for skill '%s': %s", entry.name, exc
                    )
                    continue
    except (AttributeError, ModuleNotFoundError, ImportError):
        logger.warning("intentkit skills package not found when building skills text")
        return "No skills available"

    # Build hierarchical text
    text_lines = []
    text_lines.append("Available Skills by Category:")
    text_lines.append("")

    for category in sorted(categories.keys()):
        text_lines.append(f"#### {category}")
        text_lines.append("")

        for skill in sorted(categories[category], key=lambda x: x["name"]):
            text_lines.append(
                f"- **{skill['name']}** ({skill['title']}): {skill['description']}"
            )
            # List individual skills under the category
            for ind in sorted(skill["individual_skills"], key=lambda x: x["name"]):
                text_lines.append(f"  - `{ind['name']}`: {ind['description']}")

        text_lines.append("")

    return "\n".join(text_lines)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_skill_listing.py -v`
Expected: PASS

**Step 5: Run lint**

Run: `ruff format intentkit/core/manager/service.py tests/core/test_skill_listing.py && ruff check --fix intentkit/core/manager/service.py tests/core/test_skill_listing.py`

---

### Task 3: Add `validate_skills()` and `sanitize_skills()` functions

**Files:**
- Modify: `intentkit/core/manager/service.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_skill_validation.py
import pytest

from intentkit.core.manager.service import sanitize_skills, validate_skills
from intentkit.utils.error import IntentKitAPIError


def test_validate_skills_accepts_valid_config():
    """Valid skills config should pass without error."""
    skills = {
        "ui": {
            "enabled": True,
            "states": {
                "ui_show_card": "public",
                "ui_ask_user": "private",
            },
        }
    }
    validate_skills(skills)  # Should not raise


def test_validate_skills_rejects_unknown_category():
    """Unknown category must raise IntentKitAPIError."""
    skills = {
        "nonexistent_category": {
            "enabled": True,
            "states": {"some_skill": "public"},
        }
    }
    with pytest.raises(IntentKitAPIError, match="nonexistent_category"):
        validate_skills(skills)


def test_validate_skills_rejects_unknown_skill_name():
    """Unknown skill name within a valid category must raise."""
    skills = {
        "ui": {
            "enabled": True,
            "states": {"fake_skill": "public"},
        }
    }
    with pytest.raises(IntentKitAPIError, match="fake_skill"):
        validate_skills(skills)


def test_validate_skills_rejects_invalid_state_value():
    """State value must be disabled/public/private."""
    skills = {
        "ui": {
            "enabled": True,
            "states": {"ui_show_card": "enabled"},
        }
    }
    with pytest.raises(IntentKitAPIError, match="ui_show_card"):
        validate_skills(skills)


def test_validate_skills_allows_none():
    """None skills should pass (no skills configured)."""
    validate_skills(None)  # Should not raise


def test_validate_skills_allows_empty():
    """Empty dict should pass."""
    validate_skills({})  # Should not raise


def test_sanitize_skills_removes_unknown_category():
    """Categories not in registry should be removed."""
    skills = {
        "ui": {"enabled": True, "states": {"ui_show_card": "public"}},
        "nonexistent": {"enabled": True, "states": {"x": "public"}},
    }
    result = sanitize_skills(skills)
    assert "ui" in result
    assert "nonexistent" not in result


def test_sanitize_skills_removes_unknown_skill():
    """Skills not in schema should be removed from states."""
    skills = {
        "ui": {
            "enabled": True,
            "states": {
                "ui_show_card": "public",
                "deleted_skill": "public",
            },
        }
    }
    result = sanitize_skills(skills)
    assert "ui_show_card" in result["ui"]["states"]
    assert "deleted_skill" not in result["ui"]["states"]


def test_sanitize_skills_removes_category_if_all_skills_gone():
    """If all skills in a category are removed, remove the category too."""
    skills = {
        "ui": {
            "enabled": True,
            "states": {"deleted_skill_1": "public", "deleted_skill_2": "public"},
        }
    }
    result = sanitize_skills(skills)
    assert "ui" not in result


def test_sanitize_skills_returns_none_for_none():
    """None input returns None."""
    assert sanitize_skills(None) is None


def test_sanitize_skills_returns_none_for_empty():
    """Empty dict returns None."""
    assert sanitize_skills({}) is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_skill_validation.py -v`
Expected: ImportError — functions don't exist yet.

**Step 3: Implement both functions**

Add to `intentkit/core/manager/service.py`:

```python
_VALID_SKILL_STATES = {"disabled", "public", "private"}


def validate_skills(skills: dict[str, Any] | None) -> None:
    """Validate that skills config only references real categories and skill names.

    Raises IntentKitAPIError(400) with a descriptive message on any invalid entry.
    """
    if not skills:
        return

    registry = get_valid_skills_registry()

    for category, config in skills.items():
        if category not in registry:
            valid_categories = ", ".join(sorted(registry.keys()))
            raise IntentKitAPIError(
                400,
                "InvalidSkillCategory",
                f"Unknown skill category '{category}'. Valid categories: {valid_categories}",
            )

        if not isinstance(config, dict):
            continue

        states = config.get("states")
        if not isinstance(states, dict):
            continue

        valid_skills = registry[category]
        for skill_name, state_value in states.items():
            if skill_name not in valid_skills:
                valid_names = ", ".join(sorted(valid_skills.keys()))
                raise IntentKitAPIError(
                    400,
                    "InvalidSkillName",
                    f"Unknown skill '{skill_name}' in category '{category}'. "
                    f"Valid skills: {valid_names}",
                )
            if state_value not in _VALID_SKILL_STATES:
                raise IntentKitAPIError(
                    400,
                    "InvalidSkillState",
                    f"Invalid state '{state_value}' for skill '{skill_name}' "
                    f"in category '{category}'. Must be one of: disabled, public, private",
                )


def sanitize_skills(skills: dict[str, Any] | None) -> dict[str, Any] | None:
    """Remove skills and categories that no longer exist in the schema.

    Returns the cleaned dict, or None if empty after cleanup.
    """
    if not skills:
        return None

    registry = get_valid_skills_registry()
    cleaned: dict[str, Any] = {}

    for category, config in skills.items():
        if category not in registry:
            continue

        if not isinstance(config, dict):
            continue

        valid_skills = registry[category]
        states = config.get("states")
        if not isinstance(states, dict):
            cleaned[category] = config
            continue

        cleaned_states = {
            name: value for name, value in states.items() if name in valid_skills
        }

        if not cleaned_states:
            # All skills in this category were removed — drop the category
            continue

        cleaned_config = dict(config)
        cleaned_config["states"] = cleaned_states
        cleaned[category] = cleaned_config

    return cleaned if cleaned else None
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_skill_validation.py -v`
Expected: PASS

**Step 5: Run lint**

Run: `ruff format intentkit/core/manager/service.py tests/core/test_skill_validation.py && ruff check --fix intentkit/core/manager/service.py tests/core/test_skill_validation.py`

---

### Task 4: Wire validation into `create_agent()`

**Files:**
- Modify: `intentkit/core/agent/management.py`

**Step 1: Write the failing test**

```python
# tests/core/test_create_agent_skill_validation.py
import pytest

from intentkit.core.agent.management import create_agent
from intentkit.models.agent import AgentCreate
from intentkit.utils.error import IntentKitAPIError

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_create_agent_rejects_invalid_skill_category():
    """Creating an agent with unknown skill category must fail."""
    agent = AgentCreate(
        id="test-skill-val-1",
        name="Skill Test",
        model="gpt-4o-mini",
        skills={"nonexistent": {"enabled": True, "states": {"x": "public"}}},
    )
    with pytest.raises(IntentKitAPIError, match="nonexistent"):
        await create_agent(agent)


@pytest.mark.bdd
async def test_create_agent_rejects_invalid_skill_name():
    """Creating an agent with unknown skill name must fail."""
    agent = AgentCreate(
        id="test-skill-val-2",
        name="Skill Test",
        model="gpt-4o-mini",
        skills={
            "ui": {"enabled": True, "states": {"fake_skill": "public"}},
        },
    )
    with pytest.raises(IntentKitAPIError, match="fake_skill"):
        await create_agent(agent)


@pytest.mark.bdd
async def test_create_agent_accepts_valid_skills():
    """Creating an agent with valid skills should succeed."""
    agent = AgentCreate(
        id="test-skill-val-3",
        name="Skill Test Valid",
        model="gpt-4o-mini",
        skills={
            "ui": {
                "enabled": True,
                "states": {"ui_show_card": "public"},
            }
        },
    )
    created, _ = await create_agent(agent)
    assert created.skills["ui"]["states"]["ui_show_card"] == "public"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/bdd/test_create_agent_skill_validation.py -v` (move file to tests/bdd/ since it needs DB)
Expected: FAIL — no validation happens, agent gets created.

Note: Actually put this file in `tests/bdd/` since it needs DB access.

**Step 3: Add validation call to `create_agent()`**

In `intentkit/core/agent/management.py`, add import and validation call:

```python
# Add to imports at top
from intentkit.core.manager.service import validate_skills

# Add in create_agent(), after the sub_agents validation block (around line 263):
    # Validate skills configuration
    if agent.skills:
        validate_skills(agent.skills)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/bdd/test_create_agent_skill_validation.py -v`
Expected: PASS

**Step 5: Run lint**

Run: `ruff format intentkit/core/agent/management.py && ruff check --fix intentkit/core/agent/management.py`

---

### Task 5: Wire sanitize into `override_agent()` and `patch_agent()`

**Files:**
- Modify: `intentkit/core/agent/management.py`

**Step 1: Write the failing test**

```python
# tests/bdd/test_agent_skill_sanitize.py
import pytest

from intentkit.core.agent.management import create_agent, override_agent, patch_agent
from intentkit.models.agent import AgentCreate, AgentUpdate

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_override_agent_sanitizes_stale_skills():
    """Override should silently remove skills that no longer exist in schema."""
    # Create agent first
    agent = AgentCreate(
        id="test-sanitize-1",
        name="Sanitize Test",
        model="gpt-4o-mini",
    )
    await create_agent(agent)

    # Override with stale skills (simulate a skill that was deleted from codebase)
    update = AgentUpdate(
        name="Sanitize Test",
        model="gpt-4o-mini",
        skills={
            "ui": {
                "enabled": True,
                "states": {
                    "ui_show_card": "public",
                    "deleted_skill": "public",  # stale
                },
            },
            "nonexistent_cat": {  # stale category
                "enabled": True,
                "states": {"x": "public"},
            },
        },
    )
    result, _ = await override_agent("test-sanitize-1", update)
    assert "nonexistent_cat" not in (result.skills or {})
    assert "deleted_skill" not in result.skills["ui"]["states"]
    assert "ui_show_card" in result.skills["ui"]["states"]


@pytest.mark.bdd
async def test_patch_agent_sanitizes_stale_skills():
    """Patch should silently remove skills that no longer exist in schema."""
    agent = AgentCreate(
        id="test-sanitize-2",
        name="Sanitize Patch",
        model="gpt-4o-mini",
    )
    await create_agent(agent)

    update = AgentUpdate(
        skills={
            "ui": {
                "enabled": True,
                "states": {
                    "ui_show_card": "public",
                    "old_skill": "public",  # stale
                },
            },
        },
    )
    result, _ = await patch_agent("test-sanitize-2", update)
    assert "old_skill" not in result.skills["ui"]["states"]
    assert "ui_show_card" in result.skills["ui"]["states"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/bdd/test_agent_skill_sanitize.py -v`
Expected: FAIL — stale skills are preserved.

**Step 3: Add sanitize calls**

In `intentkit/core/agent/management.py`:

```python
# Add to imports
from intentkit.core.manager.service import sanitize_skills, validate_skills

# In override_agent(), before the `for key, value in update_data.items():` loop:
        if "skills" in update_data and update_data["skills"]:
            update_data["skills"] = sanitize_skills(update_data["skills"])

# In patch_agent(), before the `for key, value in update_data.items():` loop:
        if "skills" in update_data and update_data["skills"]:
            update_data["skills"] = sanitize_skills(update_data["skills"])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/bdd/test_agent_skill_sanitize.py -v`
Expected: PASS

**Step 5: Run lint**

Run: `ruff format intentkit/core/agent/management.py && ruff check --fix intentkit/core/agent/management.py`

---

### Task 6: Improve agent manager prompt

**Files:**
- Modify: `intentkit/core/lead/sub_agents/agent_manager.py`

**Step 1: Update the prompt**

Replace the `### Skill Configuration` and `### Agent Creation` sections in the prompt string with clearer instructions:

```python
    prompt = (
        "### Workflow\n\n"
        "- Call `lead_list_team_agents` first when asked about existing agents.\n"
        "- Call `lead_get_team_agent` before updating to see current config.\n\n"
        "### Agent Creation\n\n"
        "Guide user through:\n"
        "1. Name, slug, and purpose\n"
        "2. Model — `lead_get_available_llms` for options. "
        "High intelligence for complex reasoning, high speed for simple tasks.\n"
        "3. Skills — ALWAYS call `lead_list_available_skills` first to see all "
        "available categories and individual skills. Pick only the skills the "
        "agent needs based on its purpose. Keep under 20.\n"
        "4. Additional settings as needed\n\n"
        "### Skill Configuration (IMPORTANT)\n\n"
        "You MUST call `lead_list_available_skills` before configuring skills. "
        "Only use skill names from that list.\n\n"
        "Format:\n"
        '```json\n'
        '{\n'
        '  "category_name": {\n'
        '    "enabled": true,\n'
        '    "states": {\n'
        '      "skill_name_1": "public",\n'
        '      "skill_name_2": "public"\n'
        '    }\n'
        '  }\n'
        '}\n'
        '```\n\n'
        "Example — enable two image skills and one twitter skill:\n"
        '```json\n'
        '{\n'
        '  "image": {"enabled": true, "states": {"image_gpt": "public", "image_gemini_flash": "public"}},\n'
        '  "twitter": {"enabled": true, "states": {"post_tweet": "public"}}\n'
        '}\n'
        '```\n\n'
        "Rules:\n"
        "- `enabled`: category-level toggle (must be `true` to activate)\n"
        "- `states`: map of individual skill names to their access level\n"
        "- Access levels: `public` (all users), `private` (owner only)\n"
        "- Only include skills you want to enable — omitted skills stay disabled\n"
        "- The backend will reject unknown categories or skill names with an error\n\n"
        "### Agent Fields Reference\n\n"
        "- `name`: Display name (max 50 chars)\n"
        "- `purpose`, `personality`, `principles`: Agent character\n"
        "- `model`: LLM model ID\n"
        "- `prompt`: Base system prompt\n"
        "- `prompt_append`: Additional system prompt (higher priority)\n"
        "- `temperature`: Randomness (0.0~2.0, lower for rigorous tasks)\n"
        "- `skills`: Skill configurations dict (see format above)\n"
        "- `slug`: URL-friendly slug (immutable once set)\n"
        "- `sub_agents`: List of sub-agent IDs or slugs\n"
        "- `sub_agent_prompt`: Instructions for how to use sub-agents\n"
        "- `enable_todo`, `enable_activity`, `enable_post`: Feature toggles\n"
        "- `enable_long_term_memory`: Enable long-term memory\n"
        "- `super_mode`: Higher recursion limit\n"
        "- `search_internet`: LLM native internet search\n"
        "- `visibility`: PRIVATE(0), TEAM(10), PUBLIC(20)\n"
    )
```

This is a prompt-only change — no test needed, just lint.

**Step 2: Run lint**

Run: `ruff format intentkit/core/lead/sub_agents/agent_manager.py && ruff check --fix intentkit/core/lead/sub_agents/agent_manager.py`

---

### Task 7: Run full test suite and lint

**Step 1: Run lint on all changed files**

Run: `ruff format intentkit/core/manager/service.py intentkit/core/agent/management.py intentkit/core/lead/sub_agents/agent_manager.py && ruff check --fix intentkit/core/manager/service.py intentkit/core/agent/management.py intentkit/core/lead/sub_agents/agent_manager.py`

**Step 2: Run type check**

Run: `basedpyright intentkit/core/manager/service.py intentkit/core/agent/management.py intentkit/core/lead/sub_agents/agent_manager.py`

**Step 3: Run unit tests**

Run: `pytest tests/core/ -v -m "not bdd"`

**Step 4: Fix any issues found**
