"""Template operations for agent templates."""

import logging
from typing import TYPE_CHECKING

from epyxid import XID
from pydantic import BaseModel
from pydantic import Field as PydanticField
from sqlalchemy import select

from intentkit.config.db import get_session
from intentkit.models.agent import Agent, AgentCore, AgentTable, AgentVisibility
from intentkit.models.template import Template, TemplateTable

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def create_template_from_agent(agent: Agent) -> Template:
    """Create a template from an existing agent.

    This function extracts the AgentCore fields from an agent and saves them
    as a new template in the database.

    Args:
        agent: The agent to create a template from

    Returns:
        Template: The created template with all AgentCore fields copied from the agent
    """
    # Extract AgentCore fields from the agent
    core_data = {}
    for field_name in AgentCore.model_fields:
        value = getattr(agent, field_name, None)
        core_data[field_name] = value

    async with get_session() as db:
        # Create new template with agent's core fields
        db_template = TemplateTable(
            id=agent.id,
            owner=agent.owner,
            team_id=agent.team_id,
            **core_data,
        )
        db.add(db_template)
        await db.commit()
        await db.refresh(db_template)
        return Template.model_validate(db_template)


async def render_agent(agent: Agent) -> Agent:
    """Render an agent by applying its template's AgentCore fields.

    This function reads the template_id from the agent, fetches the template,
    and overlays the template's AgentCore fields onto the agent. The `name`
    and `picture` fields are only overwritten if the agent doesn't already
    have them set.

    Args:
        agent: The agent to render with template data

    Returns:
        Agent: The agent with template's AgentCore fields applied

    Note:
        If the agent has no template_id or the template is not found,
        the original agent is returned unchanged.
    """
    # Get template_id from the agent
    # Since Agent model may not have template_id mapped, we query from DB
    async with get_session() as db:
        result = await db.execute(
            select(AgentTable.template_id).where(AgentTable.id == agent.id)
        )
        row = result.first()
        if row is None:
            return agent
        template_id = row[0]

    if not template_id:
        return agent

    # Fetch the template
    async with get_session() as db:
        template_row = await db.scalar(
            select(TemplateTable).where(TemplateTable.id == template_id)
        )
        if template_row is None:
            logger.warning(f"Template '{template_id}' not found for agent '{agent.id}'")
            return agent

        template = Template.model_validate(template_row)

    # Create a dict of agent's current values for modification
    agent_data = agent.model_dump()

    # Overlay template's AgentCore fields onto the agent
    for field_name in AgentCore.model_fields:
        template_value = getattr(template, field_name, None)

        # Special handling for name and picture: only overwrite if agent doesn't have them
        if field_name in ("name", "picture"):
            current_value = getattr(agent, field_name, None)
            if current_value is not None:
                # Agent already has this field, don't overwrite
                continue

        # Overwrite with template value
        agent_data[field_name] = template_value

    # Return a new Agent instance with the merged data
    return Agent.model_validate(agent_data)


class AgentCreationFromTemplate(BaseModel):
    """Data structure for creating an agent from a template."""

    template_id: str = PydanticField(
        description="ID of the template to create the agent from"
    )
    name: str | None = PydanticField(
        default=None,
        description="Name of the agent (overrides template name if provided)",
    )
    picture: str | None = PydanticField(
        default=None,
        description="Picture URL for the agent (overrides template picture if provided)",
    )
    description: str | None = PydanticField(
        default=None, description="Description of the agent"
    )
    readonly_wallet_address: str | None = PydanticField(
        default=None, description="Read-only wallet address for the agent"
    )
    weekly_spending_limit: float | None = PydanticField(
        default=None, description="Weekly spending limit for the agent"
    )
    extra_prompt: str | None = PydanticField(
        default=None,
        description="Additional prompt text to be injected into the system prompt",
    )


async def create_agent_from_template(
    data: AgentCreationFromTemplate,
    owner: str | None = None,
    team_id: str | None = None,
) -> Agent:
    """Create a new agent from a template.

    Args:
        data: The data for creating the agent
        owner: The owner of the new agent
        team_id: The team ID of the new agent

    Returns:
        Agent: The created agent
    """
    async with get_session() as db:
        # Verify template exists
        template_exists = await db.scalar(
            select(TemplateTable.id).where(TemplateTable.id == data.template_id)
        )
        if template_exists is None:
            raise ValueError(f"Template '{data.template_id}' not found")

        # Set visibility based on team_id
        visibility = AgentVisibility.TEAM if team_id else AgentVisibility.PRIVATE

        # Create new agent with only user-provided fields
        # Template's AgentCore fields will be applied dynamically via render_agent
        db_agent = AgentTable(
            id=str(XID()),
            owner=owner,
            team_id=team_id,
            template_id=data.template_id,
            name=data.name,
            picture=data.picture,
            description=data.description,
            readonly_wallet_address=data.readonly_wallet_address,
            weekly_spending_limit=data.weekly_spending_limit,
            extra_prompt=data.extra_prompt,
            visibility=visibility,
        )
        db.add(db_agent)
        await db.commit()
        await db.refresh(db_agent)
        agent = Agent.model_validate(db_agent)
        agent = await render_agent(agent)

        # Process agent wallet
        from intentkit.core.agent import process_agent_wallet

        _ = await process_agent_wallet(agent)

        return agent
