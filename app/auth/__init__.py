import logging

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from intentkit.models.agent_data import AgentData
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


class AgentToken(BaseModel):
    """Agent token information."""

    agent_id: str
    is_public: bool


agent_security = HTTPBearer()


async def verify_agent_token(
    credentials: HTTPAuthorizationCredentials = Depends(agent_security),
) -> AgentToken:
    """Verify the API token and return the associated agent token information.

    Args:
        credentials: The Bearer token credentials from HTTPBearer

    Returns:
        AgentToken: The agent token information containing agent_id and is_public

    Raises:
        IntentKitAPIError: If token is invalid or agent not found
    """
    token = credentials.credentials

    # Find agent data by api_key
    agent_data = await AgentData.get_by_api_key(token)
    if not agent_data:
        raise IntentKitAPIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            key="InvalidAPIToken",
            message="Invalid API token",
        )

    # Check if token is public (starts with 'pk-')
    is_public = token.startswith("pk-")

    return AgentToken(agent_id=agent_data.id, is_public=is_public)
