"""Team API authentication dependencies."""

import logging

import jwt
from fastapi import Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from intentkit.config.config import config
from intentkit.core.team.membership import check_permission
from intentkit.models.team import TeamRole
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


def _get_jwt_signing_key() -> str:
    """Get the Supabase JWT signing key from config."""
    if not config.supabase_jwt_signing_key:
        raise IntentKitAPIError(
            status_code=500,
            key="ConfigMissing",
            message="SUPABASE_JWT_SIGNING_KEY is not configured",
        )
    return config.supabase_jwt_signing_key


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> str:
    """Verify Supabase JWT and return the user ID (sub claim).

    Raises:
        IntentKitAPIError 401 if token is missing, invalid, or expired.
    """
    token = credentials.credentials
    if not token:
        raise IntentKitAPIError(
            status_code=401,
            key="MissingToken",
            message="Missing authorization token",
        )

    # Debug mode for local development
    if token == "debug" and request.url.hostname == "localhost":
        logger.warning("Debug token used, returning 'system' user")
        return "system"

    signing_key = _get_jwt_signing_key()

    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise IntentKitAPIError(
            status_code=401,
            key="TokenExpired",
            message="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        logger.info("Invalid JWT token: %s", e)
        raise IntentKitAPIError(
            status_code=401,
            key="InvalidToken",
            message="Invalid token",
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise IntentKitAPIError(
            status_code=401,
            key="InvalidToken",
            message="Token missing sub claim",
        )

    return user_id


async def verify_team_member(
    team_id: str = Path(..., description="Team ID"),
    user_id: str = Depends(get_current_user),
) -> tuple[str, str]:
    """Verify that the current user is a member of the team.

    Returns (user_id, team_id) tuple.

    Raises:
        IntentKitAPIError 403 if the user is not a team member.
    """
    is_member = await check_permission(team_id, user_id, TeamRole.MEMBER)
    if not is_member:
        raise IntentKitAPIError(
            status_code=403,
            key="NotTeamMember",
            message="Not a member of this team",
        )
    return (user_id, team_id)


async def verify_team_admin(
    team_id: str = Path(..., description="Team ID"),
    user_id: str = Depends(get_current_user),
) -> tuple[str, str]:
    """Verify that the current user is an admin or owner of the team.

    Returns (user_id, team_id) tuple.

    Raises:
        IntentKitAPIError 403 if the user is not an admin or owner.
    """
    is_admin = await check_permission(team_id, user_id, TeamRole.ADMIN)
    if not is_admin:
        raise IntentKitAPIError(
            status_code=403,
            key="NotTeamAdmin",
            message="Admin or owner role required",
        )
    return (user_id, team_id)
