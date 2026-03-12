"""
BDD Tests: Agent Slug Management

Feature: Agent Slug as a First-Class Identifier
As an IntentKit operator, I want to use slugs as unique, immutable identifiers
so that agents can be referenced by human-readable URLs.
"""

import pytest

from intentkit.core.agent import (
    create_agent,
    get_agent_by_id_or_slug,
    override_agent,
    patch_agent,
)
from intentkit.models.agent import AgentCreate, AgentUpdate
from intentkit.utils.error import IntentKitAPIError

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_create_agent_with_slug():
    """
    Scenario: Create Agent with Slug

    Given a clean database
    When I create an agent with slug="slug-test"
    Then the agent is persisted with that slug
    """
    agent_data = AgentCreate(
        id="slug-create-test",
        name="Slug Test Agent",
        model="gpt-4o-mini",
        slug="slug-test",
    )
    agent, _ = await create_agent(agent_data)

    assert agent.slug == "slug-test"


@pytest.mark.bdd
async def test_create_agent_without_slug():
    """
    Scenario: Create Agent without Slug

    When I create an agent without setting slug
    Then the agent has slug=None
    """
    agent_data = AgentCreate(
        id="slug-none-test",
        name="No Slug Agent",
        model="gpt-4o-mini",
    )
    agent, _ = await create_agent(agent_data)

    assert agent.slug is None


@pytest.mark.bdd
async def test_create_agent_duplicate_slug_fails():
    """
    Scenario: Create Agent with Duplicate Slug Fails

    Given an agent with slug="unique-slug" exists
    When I create another agent with slug="unique-slug"
    Then a SlugAlreadyExists error is raised
    """
    agent1 = AgentCreate(
        id="slug-dup-first",
        name="First Agent",
        model="gpt-4o-mini",
        slug="unique-slug",
    )
    await create_agent(agent1)

    agent2 = AgentCreate(
        id="slug-dup-second",
        name="Second Agent",
        model="gpt-4o-mini",
        slug="unique-slug",
    )
    with pytest.raises(IntentKitAPIError) as exc_info:
        await create_agent(agent2)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "SlugAlreadyExists"


@pytest.mark.bdd
async def test_patch_agent_set_slug():
    """
    Scenario: Set Slug via Patch

    Given an agent with no slug
    When I patch it to set slug="new-slug"
    Then the agent has slug="new-slug"
    """
    agent_data = AgentCreate(
        id="slug-patch-set",
        name="Patch Slug Agent",
        model="gpt-4o-mini",
    )
    await create_agent(agent_data)

    update = AgentUpdate(name="Patch Slug Agent", model="gpt-4o-mini", slug="new-slug")
    patched, _ = await patch_agent("slug-patch-set", update)

    assert patched.slug == "new-slug"


@pytest.mark.bdd
async def test_patch_agent_slug_immutable():
    """
    Scenario: Slug Cannot Be Changed Once Set

    Given an agent with slug="immutable-slug"
    When I patch it to set slug="different-slug"
    Then a SlugImmutable error is raised
    """
    agent_data = AgentCreate(
        id="slug-immutable-test",
        name="Immutable Slug Agent",
        model="gpt-4o-mini",
        slug="immutable-slug",
    )
    await create_agent(agent_data)

    update = AgentUpdate(
        name="Immutable Slug Agent", model="gpt-4o-mini", slug="different-slug"
    )
    with pytest.raises(IntentKitAPIError) as exc_info:
        await patch_agent("slug-immutable-test", update)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "SlugImmutable"


@pytest.mark.bdd
async def test_patch_agent_slug_same_value_ok():
    """
    Scenario: Setting Slug to Same Value Does Not Error

    Given an agent with slug="keep-slug"
    When I patch it with slug="keep-slug" (same value)
    Then no error is raised
    """
    agent_data = AgentCreate(
        id="slug-same-test",
        name="Same Slug Agent",
        model="gpt-4o-mini",
        slug="keep-slug",
    )
    await create_agent(agent_data)

    update = AgentUpdate(name="Same Slug Agent", model="gpt-4o-mini", slug="keep-slug")
    patched, _ = await patch_agent("slug-same-test", update)
    assert patched.slug == "keep-slug"


@pytest.mark.bdd
async def test_override_agent_slug_immutable():
    """
    Scenario: Override Cannot Change Slug

    Given an agent with slug="override-slug"
    When I override it with slug="changed-slug"
    Then a SlugImmutable error is raised
    """
    agent_data = AgentCreate(
        id="slug-override-test",
        name="Override Slug Agent",
        model="gpt-4o-mini",
        slug="override-slug",
    )
    await create_agent(agent_data)

    update = AgentUpdate(
        name="Override Slug Agent", model="gpt-4o-mini", slug="changed-slug"
    )
    with pytest.raises(IntentKitAPIError) as exc_info:
        await override_agent("slug-override-test", update)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "SlugImmutable"


@pytest.mark.bdd
async def test_patch_agent_duplicate_slug_fails():
    """
    Scenario: Patch Slug to Existing Slug Fails

    Given agent-a with slug="taken-slug" and agent-b with no slug
    When I patch agent-b to set slug="taken-slug"
    Then a SlugAlreadyExists error is raised
    """
    agent_a = AgentCreate(
        id="slug-taken-a",
        name="Agent A",
        model="gpt-4o-mini",
        slug="taken-slug",
    )
    await create_agent(agent_a)

    agent_b = AgentCreate(
        id="slug-taken-b",
        name="Agent B",
        model="gpt-4o-mini",
    )
    await create_agent(agent_b)

    update = AgentUpdate(name="Agent B", model="gpt-4o-mini", slug="taken-slug")
    with pytest.raises(IntentKitAPIError) as exc_info:
        await patch_agent("slug-taken-b", update)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "SlugAlreadyExists"


@pytest.mark.bdd
async def test_get_agent_by_slug():
    """
    Scenario: Retrieve Agent by Slug

    Given an agent with id="slug-get-test" and slug="findme"
    When I call get_agent_by_id_or_slug("findme")
    Then the correct agent is returned
    """
    agent_data = AgentCreate(
        id="slug-get-test",
        name="Find Me Agent",
        model="gpt-4o-mini",
        slug="findme",
    )
    await create_agent(agent_data)

    agent = await get_agent_by_id_or_slug("findme")

    assert agent is not None
    assert agent.id == "slug-get-test"
    assert agent.slug == "findme"


@pytest.mark.bdd
async def test_get_agent_by_id_still_works():
    """
    Scenario: Retrieve Agent by ID (Not Slug)

    Given an agent with id="slug-id-get" and slug="by-id-test"
    When I call get_agent_by_id_or_slug("slug-id-get")
    Then the correct agent is returned
    """
    agent_data = AgentCreate(
        id="slug-id-get",
        name="By ID Agent",
        model="gpt-4o-mini",
        slug="by-id-test",
    )
    await create_agent(agent_data)

    agent = await get_agent_by_id_or_slug("slug-id-get")

    assert agent is not None
    assert agent.id == "slug-id-get"


@pytest.mark.bdd
async def test_get_agent_by_slug_not_found():
    """
    Scenario: Non-Existent Slug Returns None

    When I call get_agent_by_id_or_slug("nonexistent-slug")
    Then None is returned
    """
    agent = await get_agent_by_id_or_slug("nonexistent-slug")
    assert agent is None
