from typing import Any, Dict, List, Optional

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.config.config import config
from intentkit.core.agent import (
    add_autonomous_task as _add_autonomous_task,
)
from intentkit.core.agent import (
    delete_autonomous_task as _delete_autonomous_task,
)
from intentkit.core.agent import (
    list_autonomous_tasks as _list_autonomous_tasks,
)
from intentkit.core.agent import (
    update_autonomous_task as _update_autonomous_task,
)
from intentkit.models.agent import Agent, AgentAutonomous
from intentkit.models.agent_data import AgentData, AgentQuota
from intentkit.models.skill import (
    AgentSkillData,
    AgentSkillDataCreate,
    ThreadSkillData,
    ThreadSkillDataCreate,
)


class SkillStore(SkillStoreABC):
    """Implementation of skill data storage operations.

    This class provides concrete implementations for storing and retrieving
    skill-related data for both agents and threads.
    """

    @staticmethod
    def get_system_config(key: str) -> Any:
        # TODO: maybe need a whitelist here
        if hasattr(config, key):
            return getattr(config, key)
        return None

    @staticmethod
    async def get_agent_config(agent_id: str) -> Optional[Agent]:
        return await Agent.get(agent_id)

    @staticmethod
    async def get_agent_data(agent_id: str) -> AgentData:
        return await AgentData.get(agent_id)

    @staticmethod
    async def set_agent_data(agent_id: str, data: Dict) -> AgentData:
        return await AgentData.patch(agent_id, data)

    @staticmethod
    async def get_agent_quota(agent_id: str) -> AgentQuota:
        return await AgentQuota.get(agent_id)

    @staticmethod
    async def get_agent_skill_data(
        agent_id: str, skill: str, key: str
    ) -> Optional[Dict[str, Any]]:
        """Get skill data for an agent.

        Args:
            agent_id: ID of the agent
            skill: Name of the skill
            key: Data key

        Returns:
            Dictionary containing the skill data if found, None otherwise
        """
        return await AgentSkillData.get(agent_id, skill, key)

    @staticmethod
    async def save_agent_skill_data(
        agent_id: str, skill: str, key: str, data: Dict[str, Any]
    ) -> None:
        """Save or update skill data for an agent.

        Args:
            agent_id: ID of the agent
            skill: Name of the skill
            key: Data key
            data: JSON data to store
        """
        skill_data = AgentSkillDataCreate(
            agent_id=agent_id,
            skill=skill,
            key=key,
            data=data,
        )
        await skill_data.save()

    @staticmethod
    async def delete_agent_skill_data(agent_id: str, skill: str, key: str) -> None:
        """Delete skill data for an agent.

        Args:
            agent_id: ID of the agent
            skill: Name of the skill
            key: Data key
        """
        await AgentSkillData.delete(agent_id, skill, key)

    @staticmethod
    async def get_thread_skill_data(
        thread_id: str, skill: str, key: str
    ) -> Optional[Dict[str, Any]]:
        """Get skill data for a thread.

        Args:
            thread_id: ID of the thread
            skill: Name of the skill
            key: Data key

        Returns:
            Dictionary containing the skill data if found, None otherwise
        """
        return await ThreadSkillData.get(thread_id, skill, key)

    @staticmethod
    async def save_thread_skill_data(
        thread_id: str,
        agent_id: str,
        skill: str,
        key: str,
        data: Dict[str, Any],
    ) -> None:
        """Save or update skill data for a thread.

        Args:
            thread_id: ID of the thread
            agent_id: ID of the agent that owns this thread
            skill: Name of the skill
            key: Data key
            data: JSON data to store
        """
        skill_data = ThreadSkillDataCreate(
            thread_id=thread_id,
            agent_id=agent_id,
            skill=skill,
            key=key,
            data=data,
        )
        await skill_data.save()

    @staticmethod
    async def list_autonomous_tasks(agent_id: str) -> List[AgentAutonomous]:
        """List all autonomous tasks for an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            List[AgentAutonomous]: List of autonomous task configurations
        """
        return await _list_autonomous_tasks(agent_id)

    @staticmethod
    async def add_autonomous_task(
        agent_id: str, task: AgentAutonomous
    ) -> AgentAutonomous:
        """Add a new autonomous task to an agent.

        Args:
            agent_id: ID of the agent
            task: Autonomous task configuration

        Returns:
            AgentAutonomous: The created task
        """
        return await _add_autonomous_task(agent_id, task)

    @staticmethod
    async def delete_autonomous_task(agent_id: str, task_id: str) -> None:
        """Delete an autonomous task from an agent.

        Args:
            agent_id: ID of the agent
            task_id: ID of the task to delete
        """
        await _delete_autonomous_task(agent_id, task_id)

    @staticmethod
    async def update_autonomous_task(
        agent_id: str, task_id: str, task_updates: dict
    ) -> AgentAutonomous:
        """Update an autonomous task for an agent.

        Args:
            agent_id: ID of the agent
            task_id: ID of the task to update
            task_updates: Dictionary containing fields to update

        Returns:
            AgentAutonomous: The updated task
        """
        return await _update_autonomous_task(agent_id, task_id, task_updates)


skill_store = SkillStore()
