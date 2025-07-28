from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from intentkit.models.agent import Agent, AgentAutonomous
from intentkit.models.agent_data import AgentData, AgentQuota


class SkillStoreABC(ABC):
    """Abstract base class for skill data storage operations.

    This class defines the interface for interacting with skill-related data
    for both agents and threads.
    """

    @staticmethod
    @abstractmethod
    def get_system_config(key: str) -> Any:
        """Get system configuration value by key."""
        pass

    @staticmethod
    @abstractmethod
    async def get_agent_config(agent_id: str) -> Optional[Agent]:
        """Get agent configuration.

        Returns:
            Agent configuration if found, None otherwise
        """
        pass

    @staticmethod
    @abstractmethod
    async def get_agent_data(agent_id: str) -> Optional[AgentData]:
        """Get additional agent data.

        Returns:
            Agent data if found, None otherwise
        """
        pass

    @staticmethod
    @abstractmethod
    async def set_agent_data(agent_id: str, data: Dict) -> None:
        """Update agent data.

        Args:
            agent_id: ID of the agent
            data: Dictionary containing fields to update
        """
        pass

    @staticmethod
    @abstractmethod
    async def get_agent_quota(agent_id: str) -> Optional[AgentQuota]:
        """Get agent quota information.

        Returns:
            Agent quota if found, None otherwise
        """
        pass

    @staticmethod
    @abstractmethod
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
        pass

    @staticmethod
    @abstractmethod
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
        pass

    @staticmethod
    @abstractmethod
    async def delete_agent_skill_data(agent_id: str, skill: str, key: str) -> None:
        """Delete skill data for an agent.

        Args:
            agent_id: ID of the agent
            skill: Name of the skill
            key: Data key
        """
        pass

    @staticmethod
    @abstractmethod
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
        pass

    @staticmethod
    @abstractmethod
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
        pass

    @staticmethod
    @abstractmethod
    async def list_autonomous_tasks(agent_id: str) -> List[AgentAutonomous]:
        """List all autonomous tasks for an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            List[AgentAutonomous]: List of autonomous task configurations
        """
        pass

    @staticmethod
    @abstractmethod
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
        pass

    @staticmethod
    @abstractmethod
    async def delete_autonomous_task(agent_id: str, task_id: str) -> None:
        """Delete an autonomous task from an agent.

        Args:
            agent_id: ID of the agent
            task_id: ID of the task to delete
        """
        pass

    @staticmethod
    @abstractmethod
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
        pass
