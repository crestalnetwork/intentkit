from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill


class VeniceAudioBaseTool(IntentKitSkill):
    """Base class for Venice Audio tools."""

    category: str = "venice_audio"

    def validate_voice_model(
        self, context, voice_model: str
    ) -> tuple[bool, dict[str, object] | None]:
        config = context.config

        selected_model = config.get("voice_model")
        custom_models = config.get("voice_model_custom", [])

        allowed_voice_models: list[str] = []

        if selected_model == "custom":
            allowed_voice_models = custom_models or []
        else:
            allowed_voice_models = [selected_model] if selected_model else []

        if voice_model not in allowed_voice_models:
            return False, {
                "error": f'"{voice_model}" is not allowed',
                "allowed": allowed_voice_models,
                "suggestion": "please try again with allowed voice model",
            }

        return True, None

    def get_api_key(self) -> str:
        if not config.venice_api_key:
            raise ToolException("Venice API key is not configured")
        return config.venice_api_key

    async def apply_rate_limit(self, context) -> None:
        """Apply rate limiting if configured in the agent's skill_config."""
        skill_config = context.agent.skill_config(self.category)
        limit_num = skill_config.get("rate_limit_number")
        limit_min = skill_config.get("rate_limit_minutes")
        if limit_num and limit_min:
            await self.user_rate_limit_by_category(limit_num, limit_min * 60)
