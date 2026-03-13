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
        model="gpt-4o-mini",
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
        model="gpt-4o-mini",
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
    update = AgentUpdate(name="New Name", model="gpt-4o-mini")
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
        update = AgentUpdate(name="New Name", model="gpt-4o-mini")
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
        model="gpt-4o-mini",
    )
    await create_agent(agent_data)

    # When
    agent = await get_agent("get-target")

    # Then
    assert agent is not None
    assert agent.id == "get-target"
    assert agent.name == "Get Target Agent"


@pytest.mark.bdd
async def test_create_agent_with_valid_sub_agents():
    """
    Scenario: Create Agent with Valid Sub-Agents

    Given a sub-agent with `id=sub-agent-helper` exists and has a purpose
    When I call `create_agent` with `sub_agents=["sub-agent-helper"]`
    Then the agent is created successfully with sub_agents set
    """
    # Given: create the sub-agent with a purpose
    helper = AgentCreate(
        id="sub-agent-helper",
        name="Helper Agent",
        model="gpt-4o-mini",
        purpose="Help with complex tasks",
    )
    await create_agent(helper)

    # When: create an agent referencing the helper
    agent_data = AgentCreate(
        id="sub-agent-parent",
        name="Parent Agent",
        model="gpt-4o-mini",
        sub_agents=["sub-agent-helper"],
    )
    agent, _ = await create_agent(agent_data)

    # Then
    assert agent.sub_agents == ["sub-agent-helper"]


@pytest.mark.bdd
async def test_create_agent_with_invalid_sub_agents_no_purpose():
    """
    Scenario: Create Agent with Sub-Agent Missing Purpose

    Given a sub-agent with `id=sub-agent-no-purpose` exists but has no purpose
    When I call `create_agent` with `sub_agents=["sub-agent-no-purpose"]`
    Then an `IntentKitAPIError` with `status_code=400` and `key=InvalidSubAgent` is raised
    """
    # Given
    no_purpose = AgentCreate(
        id="sub-agent-no-purpose",
        name="No Purpose Agent",
        model="gpt-4o-mini",
    )
    await create_agent(no_purpose)

    # When/Then
    with pytest.raises(IntentKitAPIError) as exc_info:
        agent_data = AgentCreate(
            id="sub-agent-parent-fail-1",
            name="Parent Agent",
            model="gpt-4o-mini",
            sub_agents=["sub-agent-no-purpose"],
        )
        await create_agent(agent_data)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "InvalidSubAgent"


@pytest.mark.bdd
async def test_create_agent_with_invalid_sub_agents_not_found():
    """
    Scenario: Create Agent with Non-Existent Sub-Agent

    Given no agent with `id=nonexistent-sub` exists
    When I call `create_agent` with `sub_agents=["nonexistent-sub"]`
    Then an `IntentKitAPIError` with `status_code=400` and `key=InvalidSubAgent` is raised
    """
    with pytest.raises(IntentKitAPIError) as exc_info:
        agent_data = AgentCreate(
            id="sub-agent-parent-fail-2",
            name="Parent Agent",
            model="gpt-4o-mini",
            sub_agents=["nonexistent-sub"],
        )
        await create_agent(agent_data)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "InvalidSubAgent"


@pytest.mark.bdd
async def test_patch_agent_sub_agents_validation():
    """
    Scenario: Patch Agent with Invalid Sub-Agents

    Given an agent with `id=patch-sub-target` exists
    When I call `patch_agent` with `sub_agents=["nonexistent"]`
    Then an `IntentKitAPIError` with `status_code=400` and `key=InvalidSubAgent` is raised
    """
    # Given
    original = AgentCreate(
        id="patch-sub-target",
        name="Patch Target",
        model="gpt-4o-mini",
    )
    await create_agent(original)

    # When/Then
    with pytest.raises(IntentKitAPIError) as exc_info:
        update = AgentUpdate(
            name="Patch Target",
            model="gpt-4o-mini",
            sub_agents=["nonexistent"],
        )
        await patch_agent("patch-sub-target", update)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "InvalidSubAgent"
