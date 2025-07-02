import logging
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def create_jwt_middleware(enable: bool, jwt_secret: str):
    """Create a JWT verification middleware with configurable enable flag and secret.

    Args:
        enable: Whether to enable JWT verification
        jwt_secret: Secret key for JWT verification

    Returns:
        A middleware function that can be used with FastAPI dependencies
    """

    async def verify_jwt(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    ) -> str:
        """Verify JWT token from Authorization header and return the subject claim.

        Returns:
            str: The subject claim from the JWT token
        """
        host = request.headers.get("host", "").split(":")[0]
        logger.debug(
            f"verify_jwt: enable={enable}, credentials={credentials}, host={host}"
        )

        if (
            not enable
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
                credentials.credentials, jwt_secret, algorithms=["HS256"]
            )
            return payload.get("sub", "")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid authentication token")

    return verify_jwt
