#!/usr/bin/env python3
"""
Batch migration script for Agent skills configuration.

This script fetches all agents from the database, migrates their skills configuration
from the old format (xxx_skills and xxx_config) to the new format where they are moved
into the skills field as a sub-dictionary, and saves them back to the database.

Usage:
  intentkit export AGENT_ID
  intentkit import AGENT_ID.yaml
"""

import asyncio
import logging

from sqlalchemy import select

from intentkit.config.config import config
from intentkit.models.agent import AgentTable
from intentkit.models.db import get_session, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def migrate_agent_skills(agent: AgentTable) -> bool:
    """
    Migrate an agent's skills from old format to new format.

    Old format:
    ```
    acolyt_skills = ["ask_gpt"]
    acolyt_config = {"api_key": "abc"}
    ```

    New format:
    ```
    skills = {
        "acolyt": {
            "states": {"ask_gpt": "public"},
            "enabled": true
        }
    }
    ```

    Args:
        agent: The agent to migrate

    Returns:
        bool: True if the agent was modified, False otherwise
    """
    # Initialize skills field if it doesn't exist
    if agent.skills is None:
        agent.skills = {}

    # Define the mapping of old skill fields to new skill names
    skill_mappings = [
        {"skills": "cdp_skills", "config": None, "name": "cdp"},
        {"skills": "twitter_skills", "config": "twitter_config", "name": "twitter"},
        {"skills": "common_skills", "config": None, "name": "common"},
        {"skills": "enso_skills", "config": "enso_config", "name": "enso"},
        {"skills": "acolyt_skills", "config": "acolyt_config", "name": "acolyt"},
        {"skills": "allora_skills", "config": "allora_config", "name": "allora"},
        {"skills": "elfa_skills", "config": "elfa_config", "name": "elfa"},
    ]

    modified = False

    # Process each skill mapping
    for mapping in skill_mappings:
        skills_field = mapping["skills"]
        config_field = mapping["config"]
        skill_name = mapping["name"]

        # Get the skills list using getattr to access the column values
        skills_list = getattr(agent, skills_field, None)

        # Skip if the skills list is empty or None
        if not skills_list:
            continue

        # Get the config if it exists
        config = getattr(agent, config_field, {}) if config_field else {}

        # Create the new skill entry
        skill_entry = {
            "states": {skill: "public" for skill in skills_list},
            "enabled": True,
        }

        # Add any config values
        if config:
            # Merge config with the skill entry
            for key, value in config.items():
                if key != "states" and key != "enabled":
                    skill_entry[key] = value

        # Add the skill entry to the skills field
        agent.skills[skill_name] = skill_entry

        # Clear the old fields
        setattr(agent, skills_field, None)
        if config_field:
            setattr(agent, config_field, None)

        modified = True

    return modified


async def batch_migrate_skills():
    """
    Fetch all agents from the database, migrate their skills, and save them back.
    """
    async with get_session() as session:
        # Fetch all agents
        result = await session.execute(select(AgentTable))
        agents = result.scalars().all()

        logger.info(f"Found {len(agents)} agents to process")

        migrated_count = 0
        for agent in agents:
            try:
                # Migrate the agent's skills
                modified = await migrate_agent_skills(agent)

                if modified:
                    # Save the agent back to the database
                    session.add(agent)
                    migrated_count += 1
                    logger.info(f"Migrated agent {agent.id} ({agent.name})")
            except Exception as e:
                logger.error(f"Error migrating agent {agent.id}: {e}")

        if migrated_count > 0:
            # Commit the changes
            await session.commit()
            logger.info(f"Successfully migrated {migrated_count} agents")
        else:
            logger.info("No agents needed migration")


async def main():
    """
    Main entry point for the script.
    """
    # Initialize the database connection
    await init_db(**config.db)

    # Run the batch migration
    await batch_migrate_skills()


if __name__ == "__main__":
    asyncio.run(main())
