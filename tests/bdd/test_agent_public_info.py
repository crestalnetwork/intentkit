"""
BDD Tests: Agent Public Info Management

Feature: Agent Public Info
As an IntentKit operator, I want to update and override agent public information
so that the agent's public-facing profile is correctly maintained.
"""

from decimal import Decimal

import pytest

from intentkit.core.agent import create_agent
from intentkit.core.agent.public_info import override_public_info, update_public_info
from intentkit.models.agent import AgentCreate, AgentPublicInfo
from intentkit.models.agent.public_info import AgentExample
from intentkit.utils.error import IntentKitAPIError

# Use session-scoped event loop to share DB connections across tests
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_update_public_info_partial():
    """
    Scenario: Update Public Info with Partial Fields

    Given a deployed agent with `id=pub-agent-1`
    When I call `update_public_info` with only `description` and `ticker`
    Then the agent's `description` and `ticker` are updated
    And other public info fields remain at their defaults
    """
    # Given
    agent_data = AgentCreate(id="pub-agent-1", name="Public Info Agent 1")
    await create_agent(agent_data)

    # When
    public_info = AgentPublicInfo(
        description="A helpful trading bot",
        ticker="TRADE",
    )
    updated_agent = await update_public_info(
        agent_id="pub-agent-1", public_info=public_info
    )

    # Then
    assert updated_agent.description == "A helpful trading bot"
    assert updated_agent.ticker == "TRADE"


@pytest.mark.bdd
async def test_update_public_info_nonexistent_agent_fails():
    """
    Scenario: Update Public Info on Non-Existent Agent Fails

    Given no agent with `id=no-such-pub-agent`
    When I call `update_public_info`
    Then an `IntentKitAPIError` with `status_code=404` is raised
    """
    public_info = AgentPublicInfo(description="Should fail")

    with pytest.raises(IntentKitAPIError) as exc_info:
        await update_public_info(agent_id="no-such-pub-agent", public_info=public_info)

    assert exc_info.value.status_code == 404


@pytest.mark.bdd
async def test_override_public_info_resets_unset_fields():
    """
    Scenario: Override Public Info Resets Unset Fields to Defaults

    Given a deployed agent with `id=pub-agent-2` that has `description` and `ticker` set
    When I call `override_public_info` with only `external_website`
    Then `external_website` is set
    And `description` and `ticker` are reset to None (defaults)
    """
    # Given
    agent_data = AgentCreate(id="pub-agent-2", name="Public Info Agent 2")
    await create_agent(agent_data)

    # First, set some fields
    await update_public_info(
        agent_id="pub-agent-2",
        public_info=AgentPublicInfo(description="Initial desc", ticker="INIT"),
    )

    # When: override with only external_website
    overridden = await override_public_info(
        agent_id="pub-agent-2",
        public_info=AgentPublicInfo(external_website="https://example.com"),
    )

    # Then
    assert overridden.external_website == "https://example.com"
    assert overridden.description is None  # Reset
    assert overridden.ticker is None  # Reset


@pytest.mark.bdd
async def test_update_public_info_with_examples():
    """
    Scenario: Update Public Info with Example Prompts

    Given a deployed agent with `id=pub-agent-3`
    When I call `update_public_info` with `examples` containing AgentExample items
    Then the agent's `examples` are correctly persisted
    """
    # Given
    agent_data = AgentCreate(id="pub-agent-3", name="Public Info Agent 3")
    await create_agent(agent_data)

    # When
    examples = [
        AgentExample(
            name="Price Check",
            description="Ask about token price",
            prompt="What is the current price of ETH?",
        ),
        AgentExample(
            name="Transfer",
            description="Send tokens",
            prompt="Send 1 USDC to 0x1234...",
        ),
    ]
    public_info = AgentPublicInfo(
        example_intro="Try these examples to get started:",
        examples=examples,
    )
    updated_agent = await update_public_info(
        agent_id="pub-agent-3", public_info=public_info
    )

    # Then
    assert updated_agent.example_intro == "Try these examples to get started:"
    assert updated_agent.examples is not None
    assert len(updated_agent.examples) == 2


@pytest.mark.bdd
async def test_partial_update_preserves_existing_fields():
    """
    Scenario: Partial Update Preserves Previously Set Fields

    Given a deployed agent with `id=pub-agent-4` that has `description` set
    When I call `update_public_info` with only `ticker`
    Then `ticker` is updated
    And `description` remains unchanged from the first update
    """
    # Given
    agent_data = AgentCreate(id="pub-agent-4", name="Public Info Agent 4")
    await create_agent(agent_data)

    await update_public_info(
        agent_id="pub-agent-4",
        public_info=AgentPublicInfo(description="Persistent description"),
    )

    # When: update only ticker
    updated_agent = await update_public_info(
        agent_id="pub-agent-4",
        public_info=AgentPublicInfo(ticker="KEEP"),
    )

    # Then
    assert updated_agent.ticker == "KEEP"
    assert updated_agent.description == "Persistent description"


@pytest.mark.bdd
async def test_public_info_updated_at_is_set():
    """
    Scenario: Public Info Updated At Timestamp Is Set

    Given a deployed agent with `id=pub-agent-5`
    When I call `update_public_info`
    Then the agent's `public_info_updated_at` is not None
    """
    # Given
    agent_data = AgentCreate(id="pub-agent-5", name="Public Info Agent 5")
    agent, _ = await create_agent(agent_data)
    assert agent.public_info_updated_at is None

    # When
    updated_agent = await update_public_info(
        agent_id="pub-agent-5",
        public_info=AgentPublicInfo(
            description="Trigger timestamp",
            fee_percentage=Decimal("2.5"),
        ),
    )

    # Then
    assert updated_agent.public_info_updated_at is not None
    assert updated_agent.fee_percentage == Decimal("2.5")
