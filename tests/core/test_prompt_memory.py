"""Tests for long-term memory and sub-agents integration in system prompt."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.abstracts.graph import AgentContext
from intentkit.core.prompt import (
    build_sub_agents_section,
    build_system_prompt,
    build_system_skills_section,
)
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

        result = build_system_skills_section(agent, context)
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

        result = build_system_skills_section(agent, context)
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

        result = build_system_skills_section(agent, context)
        assert "update_memory" not in result

    def test_excludes_call_agent_from_system_skills_section(self):
        agent = MagicMock()
        agent.enable_activity = True
        agent.enable_post = True
        agent.enable_long_term_memory = False
        agent.skills = None
        agent.telegram_entrypoint_enabled = False

        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = build_system_skills_section(agent, context)
        assert "call_agent" not in result


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
        agent.sub_agents = None

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
        agent.sub_agents = None

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
        agent.sub_agents = None

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
    def _make_agent(self, **overrides):
        agent = MagicMock()
        agent.enable_activity = overrides.get("enable_activity", True)
        agent.enable_post = overrides.get("enable_post", True)
        agent.enable_long_term_memory = overrides.get("enable_long_term_memory", False)
        agent.sub_agents = overrides.get("sub_agents", None)
        agent.search_internet = overrides.get("search_internet", True)
        return agent

    def test_includes_update_memory_when_enabled(self):
        agent = self._make_agent(enable_long_term_memory=True)
        skills = get_system_skills(agent)
        skill_names = [s.name for s in skills]
        assert "update_memory" in skill_names

    def test_excludes_update_memory_by_default(self):
        agent = self._make_agent()
        skills = get_system_skills(agent)
        skill_names = [s.name for s in skills]
        assert "update_memory" not in skill_names

    def test_excludes_update_memory_when_disabled(self):
        agent = self._make_agent(enable_long_term_memory=False)
        skills = get_system_skills(agent)
        skill_names = [s.name for s in skills]
        assert "update_memory" not in skill_names

    def test_includes_call_agent_when_sub_agents_enabled(self):
        agent = self._make_agent(sub_agents=["helper-bot"])
        skills = get_system_skills(agent)
        skill_names = [s.name for s in skills]
        assert "call_agent" in skill_names

    def test_excludes_call_agent_by_default(self):
        agent = self._make_agent()
        skills = get_system_skills(agent)
        skill_names = [s.name for s in skills]
        assert "call_agent" not in skill_names


class TestSubAgentsPromptSection:
    @pytest.mark.asyncio
    async def test_sub_agents_section_excluded_when_empty(self):
        agent = MagicMock()
        agent.sub_agents = None

        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = await build_sub_agents_section(agent, context)
        assert result == ""

    @pytest.mark.asyncio
    async def test_sub_agents_section_excluded_when_empty_list(self):
        agent = MagicMock()
        agent.sub_agents = []

        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = await build_sub_agents_section(agent, context)
        assert result == ""

    @pytest.mark.asyncio
    async def test_sub_agents_section_not_shown_in_public_context(self):
        agent = MagicMock()
        agent.sub_agents = ["helper-bot"]

        context = MagicMock(spec=AgentContext)
        context.is_private = False

        result = await build_sub_agents_section(agent, context)
        assert result == ""

    @pytest.mark.asyncio
    async def test_sub_agents_section_included_when_configured(self):
        agent = MagicMock()
        agent.sub_agents = ["helper-bot"]
        agent.sub_agent_prompt = None

        target_agent = MagicMock()
        target_agent.purpose = "Help with tasks"

        context = MagicMock(spec=AgentContext)
        context.is_private = True

        with patch(
            "intentkit.core.agent.queries.get_agent_by_id_or_slug",
            new_callable=AsyncMock,
            return_value=target_agent,
        ):
            result = await build_sub_agents_section(agent, context)

        assert "## Sub-Agents" in result
        assert "call_agent" in result
        assert "helper-bot" in result

    @pytest.mark.asyncio
    async def test_sub_agents_section_includes_purpose(self):
        agent = MagicMock()
        agent.sub_agents = ["helper-bot"]
        agent.sub_agent_prompt = None

        target_agent = MagicMock()
        target_agent.purpose = "Help with complex tasks"

        context = MagicMock(spec=AgentContext)
        context.is_private = True

        with patch(
            "intentkit.core.agent.queries.get_agent_by_id_or_slug",
            new_callable=AsyncMock,
            return_value=target_agent,
        ):
            result = await build_sub_agents_section(agent, context)

        assert "helper-bot: Help with complex tasks" in result

    @pytest.mark.asyncio
    async def test_sub_agents_section_includes_custom_prompt(self):
        agent = MagicMock()
        agent.sub_agents = ["helper-bot"]
        agent.sub_agent_prompt = "Always delegate math questions."

        target_agent = MagicMock()
        target_agent.purpose = "Math helper"

        context = MagicMock(spec=AgentContext)
        context.is_private = True

        with patch(
            "intentkit.core.agent.queries.get_agent_by_id_or_slug",
            new_callable=AsyncMock,
            return_value=target_agent,
        ):
            result = await build_sub_agents_section(agent, context)

        assert "Always delegate math questions." in result

    @pytest.mark.asyncio
    async def test_sub_agents_section_in_full_prompt(self):
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
        agent.sub_agents = ["helper-bot"]
        agent.sub_agent_prompt = None

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

        target_agent = MagicMock()
        target_agent.purpose = "Help with tasks"

        with (
            patch(
                "intentkit.core.prompt.config",
                MagicMock(
                    intentkit_prompt=None,
                    system_prompt=None,
                    tg_system_prompt=None,
                    xmtp_system_prompt=None,
                ),
            ),
            patch(
                "intentkit.core.agent.queries.get_agent_by_id_or_slug",
                new_callable=AsyncMock,
                return_value=target_agent,
            ),
        ):
            result = await build_system_prompt(agent, agent_data, context)

        assert "## Sub-Agents" in result
        assert "helper-bot: Help with tasks" in result
