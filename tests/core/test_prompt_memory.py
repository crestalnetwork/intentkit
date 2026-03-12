"""Tests for long-term memory integration in system prompt."""

from unittest.mock import MagicMock, patch

import pytest

from intentkit.abstracts.graph import AgentContext
from intentkit.core.prompt import _build_system_skills_section, build_system_prompt
from intentkit.core.system_skills import get_system_skills


class TestSystemSkillsSection:
    def test_includes_update_memory_when_enabled(self):
        agent = MagicMock()
        agent.enable_activity = True
        agent.enable_post = True
        agent.enable_long_term_memory = True
        agent.skills = None
        agent.telegram_entrypoint_enabled = False

        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = _build_system_skills_section(agent, context)
        assert "update_memory" in result

    def test_excludes_update_memory_when_disabled(self):
        agent = MagicMock()
        agent.enable_activity = True
        agent.enable_post = True
        agent.enable_long_term_memory = False
        agent.skills = None
        agent.telegram_entrypoint_enabled = False

        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = _build_system_skills_section(agent, context)
        assert "update_memory" not in result

    def test_excludes_update_memory_when_none(self):
        agent = MagicMock()
        agent.enable_activity = True
        agent.enable_post = True
        agent.enable_long_term_memory = None
        agent.skills = None
        agent.telegram_entrypoint_enabled = False

        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = _build_system_skills_section(agent, context)
        assert "update_memory" not in result


class TestBuildSystemPromptMemory:
    @pytest.mark.asyncio
    async def test_includes_memory_section_when_enabled_with_content(self):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "Test"
        agent.ticker = None
        agent.enable_long_term_memory = True
        agent.enable_activity = True
        agent.enable_post = True
        agent.skills = None
        agent.telegram_entrypoint_enabled = False
        agent.purpose = None
        agent.personality = None
        agent.principles = None
        agent.prompt = None
        agent.prompt_append = None
        agent.extra_prompt = None

        agent_data = MagicMock()
        agent_data.long_term_memory = "### Facts\n\nUser likes Python."
        agent_data.twitter_id = None
        agent_data.telegram_id = None
        agent_data.evm_wallet_address = None
        agent_data.solana_wallet_address = None
        agent_data.twitter_is_verified = False

        context = MagicMock(spec=AgentContext)
        context.is_private = True
        context.entrypoint = None
        context.chat_id = "chat-1"
        context.user_id = None

        with patch(
            "intentkit.core.prompt.config",
            MagicMock(
                intentkit_prompt=None,
                system_prompt=None,
                tg_system_prompt=None,
                xmtp_system_prompt=None,
            ),
        ):
            result = await build_system_prompt(agent, agent_data, context)

        assert "## Memory" in result
        assert "update_memory" in result
        assert "User likes Python" in result

    @pytest.mark.asyncio
    async def test_includes_memory_section_when_enabled_without_content(self):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "Test"
        agent.ticker = None
        agent.enable_long_term_memory = True
        agent.enable_activity = True
        agent.enable_post = True
        agent.skills = None
        agent.telegram_entrypoint_enabled = False
        agent.purpose = None
        agent.personality = None
        agent.principles = None
        agent.prompt = None
        agent.prompt_append = None
        agent.extra_prompt = None

        agent_data = MagicMock()
        agent_data.long_term_memory = None
        agent_data.twitter_id = None
        agent_data.telegram_id = None
        agent_data.evm_wallet_address = None
        agent_data.solana_wallet_address = None
        agent_data.twitter_is_verified = False

        context = MagicMock(spec=AgentContext)
        context.is_private = True
        context.entrypoint = None
        context.chat_id = "chat-1"
        context.user_id = None

        with patch(
            "intentkit.core.prompt.config",
            MagicMock(
                intentkit_prompt=None,
                system_prompt=None,
                tg_system_prompt=None,
                xmtp_system_prompt=None,
            ),
        ):
            result = await build_system_prompt(agent, agent_data, context)

        assert "## Memory" in result
        assert "update_memory" in result

    @pytest.mark.asyncio
    async def test_no_memory_section_when_disabled(self):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "Test"
        agent.ticker = None
        agent.enable_long_term_memory = False
        agent.enable_activity = True
        agent.enable_post = True
        agent.skills = None
        agent.telegram_entrypoint_enabled = False
        agent.purpose = None
        agent.personality = None
        agent.principles = None
        agent.prompt = None
        agent.prompt_append = None
        agent.extra_prompt = None

        agent_data = MagicMock()
        agent_data.long_term_memory = "some memory"
        agent_data.twitter_id = None
        agent_data.telegram_id = None
        agent_data.evm_wallet_address = None
        agent_data.solana_wallet_address = None
        agent_data.twitter_is_verified = False

        context = MagicMock(spec=AgentContext)
        context.is_private = True
        context.entrypoint = None
        context.chat_id = "chat-1"
        context.user_id = None

        with patch(
            "intentkit.core.prompt.config",
            MagicMock(
                intentkit_prompt=None,
                system_prompt=None,
                tg_system_prompt=None,
                xmtp_system_prompt=None,
            ),
        ):
            result = await build_system_prompt(agent, agent_data, context)

        assert "## Memory" not in result


class TestGetSystemSkills:
    def test_includes_update_memory_when_enabled(self):
        skills = get_system_skills(enable_long_term_memory=True)
        skill_names = [s.name for s in skills]
        assert "update_memory" in skill_names

    def test_excludes_update_memory_by_default(self):
        skills = get_system_skills()
        skill_names = [s.name for s in skills]
        assert "update_memory" not in skill_names

    def test_excludes_update_memory_when_disabled(self):
        skills = get_system_skills(enable_long_term_memory=False)
        skill_names = [s.name for s in skills]
        assert "update_memory" not in skill_names
