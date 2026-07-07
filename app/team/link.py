"""Team API: Links — external app accounts linked via Composio.

Members can see the Links page (team-level links plus their own user-level
ones). Team-level apps are linked/unlinked by admins; user-level apps by each
member for themselves — the level checks live in ``core.team.link``. The
complete endpoint is not team-scoped (the callback only carries the Composio
connected account id, which routes to its pending link row);
``complete_team_link`` authorizes the caller against that row's team.
"""

import logging

from fastapi import APIRouter, Body, Depends, Path, Response, status
from pydantic import BaseModel

from intentkit.clients.composio import ComposioNotConfiguredError
from intentkit.core.team.link import (
    LinkForbiddenError,
    LinkStateError,
    TeamLinksResponse,
    complete_team_link,
    delete_team_link,
    initiate_team_link,
    list_team_links,
)
from intentkit.utils.error import IntentKitAPIError

from app.team.auth import get_current_user, verify_team_member

logger = logging.getLogger(__name__)

team_link_router = APIRouter()


@team_link_router.get(
    "/teams/{team_id}/lead/links",
    response_model=TeamLinksResponse,
    operation_id="team_list_links",
    summary="List linkable apps and linked accounts (Team)",
    tags=["Lead"],
)
async def list_links(
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Get the whitelisted apps with the accounts visible to the caller:
    team-level links plus the caller's own user-level links."""
    user_id, team_id = auth
    return await list_team_links(team_id, user_id)


class LinkConnectResponse(BaseModel):
    """The Composio auth URL the caller's browser must visit to link."""

    url: str


@team_link_router.post(
    "/teams/{team_id}/lead/links/{app}/connect",
    response_model=LinkConnectResponse,
    operation_id="team_connect_link",
    summary="Start linking an external app account (Team)",
    tags=["Lead"],
)
async def connect_link(
    app: str = Path(..., description="Whitelisted app key (e.g. gmail)"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Initiate the link flow for a whitelisted app; returns the redirect URL.

    Any member may link user-level apps for themselves; team-level apps
    require an admin (enforced in the core layer).
    """
    user_id, team_id = auth
    try:
        url = await initiate_team_link(team_id, app, user_id)
    except ComposioNotConfiguredError as e:
        raise IntentKitAPIError(
            status_code=400, key="ComposioNotConfigured", message=str(e)
        )
    except LinkStateError as e:
        raise IntentKitAPIError(status_code=400, key="InvalidLinkApp", message=str(e))
    except LinkForbiddenError as e:
        raise IntentKitAPIError(status_code=403, key="LinkForbidden", message=str(e))
    except Exception:
        logger.exception("Link initiation failed for team %s app %s", team_id, app)
        raise IntentKitAPIError(
            status_code=502,
            key="LinkInitiationFailed",
            message="Could not start the link flow. Please try again.",
        )
    return LinkConnectResponse(url=url)


@team_link_router.delete(
    "/teams/{team_id}/lead/links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="team_delete_link",
    summary="Unlink an external app account (Team)",
    tags=["Lead"],
)
async def delete_link(
    link_id: str = Path(..., description="Link ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Unlink an account: removed at Composio and from the team.

    Team-level links require an admin; user-level links may be removed by
    their owning user or an admin (enforced in the core layer).
    """
    user_id, team_id = auth
    try:
        await delete_team_link(team_id, link_id, user_id)
    except LinkStateError as e:
        raise IntentKitAPIError(status_code=404, key="LinkNotFound", message=str(e))
    except LinkForbiddenError as e:
        raise IntentKitAPIError(status_code=403, key="LinkForbidden", message=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class LinkCompleteRequest(BaseModel):
    """The ``connected_account_id`` from Composio's callback redirect, relayed
    by the SPA's OAuth landing page on behalf of the signed-in user."""

    connected_account_id: str


class LinkCompleteResponse(BaseModel):
    """Which team/app the completed link bound, so the SPA can route back."""

    team_id: str
    app: str


# Not team-scoped: the pending link row (keyed by the connected account id)
# routes the completion to its team, mirroring how the channel OAuth complete
# reads the team from the signed state.
@team_link_router.post(
    "/lead/links/complete",
    response_model=LinkCompleteResponse,
    operation_id="team_complete_link",
    summary="Complete an external app account link (Team)",
    tags=["Lead"],
)
async def complete_link(
    body: LinkCompleteRequest = Body(...),
    user_id: str = Depends(get_current_user),
):
    """Finish a link attempt for the signed-in user.

    Completion requires the caller to be the user who initiated the attempt
    (an admin for team-level apps), and the account status is verified
    directly against Composio — nothing from the redirect's query string is
    trusted.
    """
    try:
        link = await complete_team_link(user_id, body.connected_account_id)
    except LinkStateError as e:
        raise IntentKitAPIError(status_code=400, key="InvalidLink", message=str(e))
    except LinkForbiddenError as e:
        raise IntentKitAPIError(status_code=403, key="LinkForbidden", message=str(e))
    except Exception:
        logger.exception("Link completion failed")
        raise IntentKitAPIError(
            status_code=400,
            key="LinkFailed",
            message="Could not complete the link. Please try again.",
        )
    return LinkCompleteResponse(team_id=link.team_id, app=link.app)
