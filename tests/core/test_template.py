from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.template import (
    AgentCreationFromTemplate,
    create_agent_from_template,
    create_template_from_agent,
    render_agent,
)
from intentkit.models.agent import Agent, AgentTable, AgentVisibility
from intentkit.models.template import Template, TemplateTable


@pytest.mark.asyncio
async def test_create_agent_from_template():
    """Test creating an agent from a template."""

    # 1. Setup Data
    template_id = "template-1"
    template_data = {
        "id": template_id,
        "name": "Template Agent",
        "description": "A template agent",
        "model": "gpt-4o",
        "temperature": 0.5,
        "prompt": "You are a template.",
    }

    # Mock TemplateTable instance
    mock_template = TemplateTable(**template_data)

    # Input data for creation
    creation_data = AgentCreationFromTemplate(
        template_id=template_id,
        name="New Agent",
        picture="new_pic.png",
        description="Created from template",
    )

    # 2. Mock Database
    with patch("intentkit.core.template.get_session") as mock_get_session:
        # Setup mock session
        mock_session = MagicMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        # Mock scalar return value
        # scalar, commit, refresh are async methods
        mock_session.scalar = AsyncMock(return_value=mock_template)
        mock_session.commit = AsyncMock()

        # Set timestamps on refresh
        async def mock_refresh(instance):
            instance.created_at = datetime.now()
            instance.updated_at = datetime.now()

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)

        # 3. Call Function
        agent = await create_agent_from_template(
            data=creation_data, owner="user_1", team_id="team_1"
        )

        # 4. Verify
        # Verify scalar called with correct select
        assert mock_session.scalar.called

        # Verify add called with expected AgentTable
        assert mock_session.add.called
        args, _ = mock_session.add.call_args
        added_agent = args[0]

        assert isinstance(added_agent, AgentTable)
        assert added_agent.template_id == template_id
        assert added_agent.owner == "user_1"
        assert added_agent.team_id == "team_1"

        # Verify visibility is set to TEAM when team_id is provided
        assert added_agent.visibility == AgentVisibility.TEAM

        # Verify overrides
        assert added_agent.name == "New Agent"
        assert added_agent.picture == "new_pic.png"
        assert added_agent.description == "Created from template"

        # Verify inherited fields
        assert added_agent.model == "gpt-4o"
        assert added_agent.temperature == 0.5
        assert added_agent.prompt == "You are a template."

        # Verify commit and refresh
        assert mock_session.commit.called
        assert mock_session.refresh.called

        # Verify returned agent match
        assert agent.id == added_agent.id


@pytest.mark.asyncio
async def test_create_agent_from_template_without_team():
    """Test creating an agent from a template without team_id (PRIVATE visibility)."""

    # 1. Setup Data
    template_id = "template-2"
    template_data = {
        "id": template_id,
        "name": "Template Agent",
        "description": "A template agent",
        "model": "gpt-4o",
        "temperature": 0.5,
        "prompt": "You are a template.",
    }

    # Mock TemplateTable instance
    mock_template = TemplateTable(**template_data)

    # Input data for creation
    creation_data = AgentCreationFromTemplate(
        template_id=template_id,
        name="Private Agent",
        picture="private_pic.png",
        description="Created without team",
    )

    # 2. Mock Database
    with patch("intentkit.core.template.get_session") as mock_get_session:
        # Setup mock session
        mock_session = MagicMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        # Mock scalar return value
        mock_session.scalar = AsyncMock(return_value=mock_template)
        mock_session.commit = AsyncMock()

        # Set timestamps on refresh
        async def mock_refresh(instance):
            instance.created_at = datetime.now()
            instance.updated_at = datetime.now()

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)

        # 3. Call Function without team_id
        await create_agent_from_template(
            data=creation_data, owner="user_2", team_id=None
        )

        # 4. Verify
        assert mock_session.add.called
        args, _ = mock_session.add.call_args
        added_agent = args[0]

        assert isinstance(added_agent, AgentTable)
        assert added_agent.owner == "user_2"
        assert added_agent.team_id is None

        # Verify visibility is set to PRIVATE when team_id is None
        assert added_agent.visibility == AgentVisibility.PRIVATE


@pytest.mark.asyncio
async def test_create_template_from_agent():
    """Test creating a template from an agent."""
    # 1. Setup Agent Data
    agent = Agent(  # pyright: ignore[reportCallIssue]
        id="agent-1",
        name="Source Agent",
        description="Agent Description",
        model="gpt-4o",
        temperature=0.8,
        prompt="You are a source agent.",
        owner="owner_1",
        team_id="team_1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    # 2. Mock Database
    with patch("intentkit.core.template.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        mock_session.commit = AsyncMock()

        # Set timestamps on refresh
        async def mock_refresh(instance):
            instance.created_at = datetime.now()
            instance.updated_at = datetime.now()

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)

        # 3. Call Function
        template = await create_template_from_agent(agent)

        # 4. Verify
        assert mock_session.add.called
        args, _ = mock_session.add.call_args
        added_template = args[0]

        assert isinstance(added_template, TemplateTable)
        # ID should match agent ID
        assert added_template.id == agent.id
        assert added_template.owner == agent.owner
        assert added_template.team_id == agent.team_id

        # Core fields copied
        assert added_template.name == agent.name
        assert added_template.model == agent.model
        assert added_template.temperature == agent.temperature
        assert added_template.prompt == agent.prompt

        assert mock_session.commit.called
        assert mock_session.refresh.called

        assert isinstance(template, Template)
        assert template.id == added_template.id


@pytest.mark.asyncio
async def test_render_agent():
    """Test rendering an agent with template data."""
    # 1. Setup Data
    template_id = "temp-1"
    template_data = {
        "id": template_id,
        "name": "Template Name",
        "picture": "template_pic.png",
        "model": "gpt-4-template",
        "temperature": 0.1,
        "prompt": "Template Prompts",
    }
    mock_template_row = TemplateTable(**template_data)

    agent = Agent(  # pyright: ignore[reportCallIssue]
        id="agent-1",
        name=None,  # Should take from template
        picture="agent_pic.png",  # Should KEEP agent's
        model="legacy-model",
        temperature=0.9,
        prompt="Legacy Prompt",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    # 2. Mock Database
    with patch("intentkit.core.template.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        # Mock execute for getting template_id
        # result.first() returns (template_id,) or None
        mock_result = MagicMock()
        mock_result.first.return_value = (template_id,)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock scalar for getting template
        mock_session.scalar = AsyncMock(return_value=mock_template_row)

        # 3. Call Function
        rendered_agent = await render_agent(agent)

        # 4. Verify
        # Name was None in agent, should take from template
        assert rendered_agent.name == "Template Name"

        # Picture was set in agent, should keep agent's
        assert rendered_agent.picture == "agent_pic.png"

        # Other core fields should be overwritten by template
        assert rendered_agent.model == "gpt-4-template"
        assert rendered_agent.temperature == 0.1
        assert rendered_agent.prompt == "Template Prompts"


@pytest.mark.asyncio
async def test_render_agent_no_template():
    """Test rendering an agent that has no template linked."""
    agent = Agent(  # pyright: ignore[reportCallIssue]
        id="agent-no-temp",
        name="Just Agent",
        model="gpt-3.5",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("intentkit.core.template.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        # Mock execute returning None (no template_id found for agent)
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        rendered_agent = await render_agent(agent)

        # Should return original agent (or identical copy)
        assert rendered_agent.name == "Just Agent"
        assert rendered_agent.model == "gpt-3.5"
