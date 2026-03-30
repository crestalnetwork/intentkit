from app.team.agent import team_agent_router
from app.team.autonomous import team_autonomous_router
from app.team.chat import team_chat_router
from app.team.content import team_content_router
from app.team.lead import team_lead_router
from app.team.public import public_router as team_public_router
from app.team.team import team_management_router
from app.team.user import team_user_router

__all__ = [
    "team_agent_router",
    "team_autonomous_router",
    "team_chat_router",
    "team_content_router",
    "team_lead_router",
    "team_management_router",
    "team_public_router",
    "team_user_router",
]
