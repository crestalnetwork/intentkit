"""Base class for lead skills."""

from __future__ import annotations

from intentkit.skills.base import IntentKitSkill


class LeadSkill(IntentKitSkill):
    """Base class for all lead skills."""

    category: str = "lead"
