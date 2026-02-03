"""Base class for manager skills."""

from __future__ import annotations

from intentkit.skills.base import IntentKitSkill


class ManagerSkill(IntentKitSkill):
    """Base class for all manager skills."""

    category: str = "manager"
