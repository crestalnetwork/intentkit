import secrets

from intentkit.skills.base import IntentKitSkill


class SystemBaseTool(IntentKitSkill):
    """Base class for system-related skills."""

    @property
    def category(self) -> str:
        """Return the skill category."""
        return "system"

    def _generate_api_key(self) -> str:
        """Generate a new API key using secure random bytes."""
        # Generate 32 random bytes and convert to hex string
        return f"sk-{secrets.token_hex(32)}"

    def _generate_public_api_key(self) -> str:
        """Generate a new public API key using secure random bytes."""
        # Generate 32 random bytes and convert to hex string
        return f"pk-{secrets.token_hex(32)}"
