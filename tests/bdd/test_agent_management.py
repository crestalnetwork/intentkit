"""
BDD Tests: Agent Lifecycle Management

Feature: Agent Lifecycle Management
As an IntentKit operator, I want to manage agents through the core API
so that I can create, update, and archive AI agents.
"""

import pytest

from intentkit.core.agent import create_agent, get_agent, patch_agent
from intentkit.models.agent import AgentCreate, AgentUpdate
from intentkit.utils.error import IntentKitAPIError

# Use session-scoped event loop to share DB connections across tests
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_create_agent_minimal_config():
    """
    Scenario: Create Agent with Minimal Config

    Given a clean `bdd` database with no agents
    When I call `create_agent` with `id=test-agent-1`, `name=Test Agent`
    Then an agent with `id=test-agent-1` is persisted in the database
    And the agent has `owner=system` (default)
    And `deployed_at` is set
    """
    # Given: clean database (handled by conftest fixture)

    # When: create agent with minimal config
    agent_data = AgentCreate(
        id="test-agent-1",
        name="Test Agent",
    )
    agent, _ = await create_agent(agent_data)

    # Then: agent is persisted
    assert agent.id == "test-agent-1"
    assert agent.name == "Test Agent"
    assert agent.owner == "system"
    assert agent.deployed_at is not None


@pytest.mark.bdd
async def test_create_agent_full_config():
    """
    Scenario: Create Agent with Full Config

    Given a clean `bdd` database
    When I call `create_agent` with id, name, model, prompt
    Then the agent is persisted with all provided fields
    """
    # When
    agent_data = AgentCreate(
        id="test-agent-full",
        name="Full Config Agent",
        model="gpt-4o-mini",
        prompt="You are a helpful assistant.",
    )
    agent, _ = await create_agent(agent_data)

    # Then
    assert agent.id == "test-agent-full"
    assert agent.name == "Full Config Agent"
    assert agent.model == "gpt-4o-mini"
    assert agent.prompt == "You are a helpful assistant."


@pytest.mark.bdd
async def test_create_duplicate_agent_fails():
    """
    Scenario: Create Duplicate Agent Fails

    Given an agent with `id=existing-agent` already exists
    When I call `create_agent` with `id=existing-agent`
    Then an `IntentKitAPIError` with `status_code=400` and `key=AgentExists` is raised
    """
    # Given: create an agent first
    agent_data = AgentCreate(
        id="existing-agent",
        name="Existing Agent",
    )
    await create_agent(agent_data)

    # When/Then: try to create duplicate
    with pytest.raises(IntentKitAPIError) as exc_info:
        await create_agent(agent_data)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "AgentExists"


@pytest.mark.bdd
async def test_patch_agent_updates_specific_fields():
    """
    Scenario: Patch Agent Updates Specific Fields

    Given an agent with `id=patch-target`, `name=Original Name`
    When I call `patch_agent` with `id=patch-target`, `name=New Name`
    Then the agent's `name` is updated to `New Name`
    And other fields remain unchanged
    """
    # Given
    original = AgentCreate(
        id="patch-target",
        name="Original Name",
        model="gpt-4o-mini",
    )
    await create_agent(original)

    # When
    update = AgentUpdate(name="New Name")
    patched_agent, _ = await patch_agent("patch-target", update)

    # Then
    assert patched_agent.name == "New Name"
    assert patched_agent.model == "gpt-4o-mini"  # unchanged


@pytest.mark.bdd
async def test_patch_nonexistent_agent_fails():
    """
    Scenario: Patch Non-Existent Agent Fails

    Given no agent with `id=non-existent`
    When I call `patch_agent` with `id=non-existent`
    Then an `IntentKitAPIError` with `status_code=404` is raised
    """
    # When/Then
    with pytest.raises(IntentKitAPIError) as exc_info:
        update = AgentUpdate(name="New Name")
        await patch_agent("non-existent", update)

    assert exc_info.value.status_code == 404


@pytest.mark.bdd
async def test_get_agent_by_id():
    """
    Scenario: Get Agent by ID

    Given an agent with `id=get-target`
    When I call `get_agent` with `id=get-target`
    Then the agent is returned with correct fields
    """
    # Given
    agent_data = AgentCreate(
        id="get-target",
        name="Get Target Agent",
    )
    await create_agent(agent_data)

    # When
    agent = await get_agent("get-target")

    # Then
    assert agent is not None
    assert agent.id == "get-target"
    assert agent.name == "Get Target Agent"
