"""Tests for long-term memory and sub-agents integration in system prompt."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.abstracts.graph import AgentContext
from intentkit.core.prompt import (
    build_sub_agents_section,
    build_system_prompt,
    build_system_skills_section,
)
from intentkit.core.system_skills import (
    call_agent,
    create_activity,
    create_post,
    current_time,
    get_post,
    recent_activities,
    recent_posts,
    update_memory,
)


class TestSystemSkillsSection:
    @staticmethod
    def _make_agent(**overrides):
        agent = MagicMock()
        agent.is_activity_enabled = overrides.get("is_activity_enabled", True)
        agent.is_post_enabled = overrides.get("is_post_enabled", True)
        agent.enable_long_term_memory = overrides.get("enable_long_term_memory", False)
        agent.skills = None
        agent.telegram_entrypoint_enabled = False
        return agent

    def test_includes_update_memory_when_enabled(self):
        agent = self._make_agent(enable_long_term_memory=True)
        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = build_system_skills_section(agent, context)
        assert "update_memory" in result

    def test_excludes_update_memory_when_disabled(self):
        agent = self._make_agent(enable_long_term_memory=False)
        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = build_system_skills_section(agent, context)
        assert "update_memory" not in result

    def test_excludes_update_memory_when_none(self):
        agent = self._make_agent(enable_long_term_memory=None)
        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = build_system_skills_section(agent, context)
        assert "update_memory" not in result

    def test_excludes_call_agent_from_system_skills_section(self):
        agent = self._make_agent()
        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = build_system_skills_section(agent, context)
        assert "call_agent" not in result

    def test_excludes_post_skills_when_disabled(self):
        agent = self._make_agent(is_post_enabled=False)
        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = build_system_skills_section(agent, context)
        assert "create_post" not in result
        assert "get_post" not in result
        assert "recent_posts" not in result

    def test_excludes_activity_skills_when_disabled(self):
        agent = self._make_agent(is_activity_enabled=False)
        context = MagicMock(spec=AgentContext)
        context.is_private = True

        result = build_system_skills_section(agent, context)
        assert "create_activity" not in result
        assert "recent_activities" not in result


class TestBuildSystemPromptMemory:
    @pytest.mark.asyncio
    async def test_includes_memory_section_when_enabled_with_content(self):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "Test"
        agent.ticker = None
        agent.enable_long_term_memory = True
        agent.is_activity_enabled = True
        agent.is_post_enabled = True
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
        agent.is_activity_enabled = True
        agent.is_post_enabled = True
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
        agent.is_activity_enabled = True
        agent.is_post_enabled = True
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


class TestSystemSkillInstances:
    """Test that system skill singleton instances are correctly initialized."""

    def test_current_time_instance(self):
        assert current_time.name == "current_time"

    def test_call_agent_instance(self):
        assert call_agent.name == "call_agent"

    def test_activity_instances(self):
        assert create_activity.name == "create_activity"
        assert recent_activities.name == "recent_activities"

    def test_post_instances(self):
        assert create_post.name == "create_post"
        assert get_post.name == "get_post"
        assert recent_posts.name == "recent_posts"

    def test_update_memory_instance(self):
        assert update_memory.name == "update_memory"


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
        agent.is_activity_enabled = True
        agent.is_post_enabled = True
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
