from abc import ABC, abstractmethod
from typing import Any

from intentkit.models.agent import Agent
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
    async def get_agent_config(agent_id: str) -> Agent | None:
        """Get agent configuration.

        Returns:
            Agent configuration if found, None otherwise
        """
        pass

    @staticmethod
    @abstractmethod
    async def get_agent_data(agent_id: str) -> AgentData | None:
        """Get additional agent data.

        Returns:
            Agent data if found, None otherwise
        """
        pass

    @staticmethod
    @abstractmethod
    async def set_agent_data(agent_id: str, data: dict[str, Any]) -> None:
        """Update agent data.

        Args:
            agent_id: ID of the agent
            data: Dictionary containing fields to update
        """
        pass

    @staticmethod
    @abstractmethod
    async def get_agent_quota(agent_id: str) -> AgentQuota | None:
        """Get agent quota information.

        Returns:
            Agent quota if found, None otherwise
        """
        pass
