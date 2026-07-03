"""Local API: Links — external app accounts for the single-user deployment.

Same feature as the team API's ``app/team/link.py``, without auth: the local
deployment has one implicit user and its lead agent lives under the synthetic
``system`` team, so every endpoint operates on that team. The Composio OAuth
callback still lands on the SPA's ``/oauth/callback`` page, which relays the
connected account id to the complete endpoint here.
"""

import logging

from fastapi import APIRouter, Body, Path, Response, status
from pydantic import BaseModel

from intentkit.clients.composio import ComposioNotConfiguredError
from intentkit.core.team.link import (
    LinkStateError,
    TeamLinksResponse,
    complete_team_link,
    delete_team_link,
    initiate_team_link,
    list_team_links,
)
from intentkit.utils.error import IntentKitAPIError

from app.local.lead import LEAD_TEAM_ID, LEAD_USER_ID

logger = logging.getLogger(__name__)

link_router = APIRouter()


@link_router.get(
    "/lead/links",
    response_model=TeamLinksResponse,
    operation_id="list_links",
    summary="List linkable apps and linked accounts",
    tags=["Lead"],
)
async def list_links():
    """Get the whitelisted apps with the currently linked accounts."""
    return await list_team_links(LEAD_TEAM_ID)


class LinkConnectResponse(BaseModel):
    """The Composio auth URL the browser must visit to link an account."""

    url: str


@link_router.post(
    "/lead/links/{app}/connect",
    response_model=LinkConnectResponse,
    operation_id="connect_link",
    summary="Start linking an external app account",
    tags=["Lead"],
)
async def connect_link(
    app: str = Path(..., description="Whitelisted app key (e.g. gmail)"),
):
    """Initiate the link flow for a whitelisted app; returns the redirect URL."""
    try:
        url = await initiate_team_link(LEAD_TEAM_ID, app, LEAD_USER_ID)
    except ComposioNotConfiguredError as e:
        raise IntentKitAPIError(
            status_code=400, key="ComposioNotConfigured", message=str(e)
        )
    except LinkStateError as e:
        raise IntentKitAPIError(status_code=400, key="InvalidLinkApp", message=str(e))
    except Exception:
        logger.exception("Link initiation failed for app %s", app)
        raise IntentKitAPIError(
            status_code=502,
            key="LinkInitiationFailed",
            message="Could not start the link flow. Please try again.",
        )
    return LinkConnectResponse(url=url)


@link_router.delete(
    "/lead/links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_link",
    summary="Unlink an external app account",
    tags=["Lead"],
)
async def delete_link(
    link_id: str = Path(..., description="Link ID"),
):
    """Unlink an account: removed at Composio and locally."""
    try:
        await delete_team_link(LEAD_TEAM_ID, link_id)
    except LinkStateError as e:
        raise IntentKitAPIError(status_code=404, key="LinkNotFound", message=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class LinkCompleteRequest(BaseModel):
    """The ``connected_account_id`` from Composio's callback redirect."""

    connected_account_id: str


class LinkCompleteResponse(BaseModel):
    """The app whose account was linked, so the SPA can show it."""

    team_id: str
    app: str


@link_router.post(
    "/lead/links/complete",
    response_model=LinkCompleteResponse,
    operation_id="complete_link",
    summary="Complete an external app account link",
    tags=["Lead"],
)
async def complete_link(
    body: LinkCompleteRequest = Body(...),
):
    """Finish a link attempt; the account status is verified against Composio.

    The single-user deployment has no team roles, so only the pending-row
    check applies (``verify_admin=False``).
    """
    try:
        link = await complete_team_link(
            LEAD_USER_ID, body.connected_account_id, verify_admin=False
        )
    except LinkStateError as e:
        raise IntentKitAPIError(status_code=400, key="InvalidLink", message=str(e))
    except Exception:
        logger.exception("Link completion failed")
        raise IntentKitAPIError(
            status_code=400,
            key="LinkFailed",
            message="Could not complete the link. Please try again.",
        )
    return LinkCompleteResponse(team_id=link.team_id, app=link.app)
