"""Team API authentication dependencies."""

import logging

import jwt
from fastapi import Depends, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from intentkit.config.config import config
from intentkit.core.team.membership import check_permission
from intentkit.models.team import TeamRole
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

# Cached JWKS client — reuses fetched keys until they expire
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """Get or create a cached PyJWKClient for Supabase JWKS verification."""
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    jwks_url = config.supabase_jwks_url
    if not jwks_url:
        # Derive from supabase_url if JWKS URL not explicitly set
        if config.supabase_url:
            jwks_url = (
                f"{config.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            )
        else:
            raise IntentKitAPIError(
                status_code=500,
                key="ConfigMissing",
                message="SUPABASE_JWKS_URL or SUPABASE_URL must be configured",
            )

    _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
    return _jwks_client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> str:
    """Verify Supabase JWT and return the user ID (sub claim).

    Verification strategy:
    1. HS256 if SUPABASE_JWT_SIGNING_KEY is configured (default for most Supabase projects)
    2. JWKS/RS256 if SUPABASE_JWKS_URL or SUPABASE_URL is configured (for RS256 projects)

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
    if token == "debug" and config.debug:
        logger.warning("Debug token used, returning 'system' user")
        return "system"

    # HS256 with explicit signing key
    if config.supabase_jwt_signing_key:
        return _verify_hs256(token)

    # JWKS/RS256 for asymmetric signing (modern Supabase default)
    if config.supabase_jwks_url or config.supabase_url:
        return _verify_jwks(token)

    raise IntentKitAPIError(
        status_code=500,
        key="ConfigMissing",
        message="SUPABASE_JWT_SIGNING_KEY or SUPABASE_JWKS_URL must be configured",
    )


def _verify_hs256(token: str) -> str:
    """Verify JWT using HS256 symmetric key."""
    signing_key = config.supabase_jwt_signing_key
    assert signing_key is not None
    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["HS256"],
            audience="authenticated",
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


def _verify_jwks(token: str) -> str:
    """Verify JWT using JWKS — supports any algorithm advertised by the JWKS endpoint."""
    client = _get_jwks_client()

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        # Use the algorithm from the JWK itself instead of hardcoding
        alg = signing_key.algorithm_name
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            audience="authenticated",
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
    except Exception as e:
        logger.error("JWKS verification error: %s", e)
        raise IntentKitAPIError(
            status_code=401,
            key="InvalidToken",
            message="Token verification failed",
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
