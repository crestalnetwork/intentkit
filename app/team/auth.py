"""Team API authentication dependencies."""

from fastapi import Depends, Header, HTTPException, Path

from intentkit.core.team.membership import check_permission
from intentkit.models.team import TeamRole

_BEARER_PREFIX = "Bearer "


async def get_current_user(
    authorization: str = Header(..., description="Bearer token"),
) -> str:
    """Extract user_id from Bearer token.

    Returns the user_id string.

    Raises:
        HTTPException 401 if token is missing or has invalid format.
    """
    if not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[len(_BEARER_PREFIX) :]
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    # TODO: Validate token and extract user_id
    return token


async def verify_team_member(
    team_id: str = Path(..., description="Team ID"),
    user_id: str = Depends(get_current_user),
) -> tuple[str, str]:
    """Verify that the current user is a member of the team.

    Returns (user_id, team_id) tuple.

    Raises:
        HTTPException 403 if the user is not a team member.
    """
    is_member = await check_permission(team_id, user_id, TeamRole.MEMBER)
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this team")
    return (user_id, team_id)
