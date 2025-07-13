import logging
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from intentkit.config.config import config
from intentkit.models.agent import Agent, AgentData

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def verify_admin_jwt(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """Verify JWT token from Authorization header and return the subject claim.

    Returns:
        str: The subject claim from the JWT token
    """
    host = request.headers.get("host", "").split(":")[0]
    logger.debug(
        f"verify_admin_jwt: enable={config.admin_auth_enabled}, credentials={credentials}, host={host}"
    )

    if (
        not config.admin_auth_enabled
        or host == "localhost"
        or host == "127.0.0.1"
        or host == "intent-api"
        or host == "intent-readonly"
        or host == "intent-singleton"
    ):
        return ""

    if not credentials:
        raise HTTPException(
            status_code=401, detail="Missing authentication credentials"
        )

    try:
        payload = jwt.decode(
            credentials.credentials, config.admin_jwt_secret, algorithms=["HS256"]
        )
        return payload.get("sub", "")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")


agent_security = HTTPBearer()


async def verify_agent_token(
    credentials: HTTPAuthorizationCredentials = Depends(agent_security),
) -> str:
    """Verify the API token and return the associated agent ID.

    Args:
        credentials: The Bearer token credentials from HTTPBearer

    Returns:
        str: The agent ID associated with the token

    Raises:
        HTTPException: If token is invalid or agent not found
    """
    token = credentials.credentials

    # Find agent data by api_key
    agent_data = await AgentData.get_by_api_key(token)
    if not agent_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token"
        )

    # Get the agent
    agent = await Agent.get(agent_data.id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )

    return agent.id
