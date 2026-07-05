"""Tests for long-term memory and sub-agents integration in system prompt."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.abstracts.graph import AgentContext
from intentkit.core.prompt import (
    _build_user_info_section,
    build_sub_agents_section,
    build_system_prompt,
    build_system_tools_section,
)
from intentkit.core.system_tools import (
    call_agent,
    create_activity,
    create_post,
    current_time,
    get_post,
    recent_activities,
    recent_posts,
    update_memory,
)
from intentkit.models.chat import AuthorType


class TestSystemToolsSection:
    @staticmethod
    def _make_agent(**overrides):
        agent = MagicMock()
        agent.is_activity_enabled = overrides.get("is_activity_enabled", True)
        agent.is_post_enabled = overrides.get("is_post_enabled", True)
        agent.enable_long_term_memory = overrides.get("enable_long_term_memory", False)
        agent.tools = None
        agent.telegram_entrypoint_enabled = False
        return agent

    def test_guest_sees_reads_but_not_writes(self):
        """Guests get the read bullets; create_* lines and the CRITICAL RULE
        caution are reserved for the owning team."""
        agent = self._make_agent()
        context = MagicMock(spec=AgentContext)
        context.is_own_team = False

        result = build_system_tools_section(agent, context)
        assert "get_post" in result
        assert "recent_posts" in result
        assert "recent_activities" in result
        assert "create_post" not in result
        assert "create_activity" not in result
        assert "CRITICAL RULE" not in result

    def test_update_memory_not_in_guide(self):
        """The Memory section documents update_memory itself; the own-team
        guide must not duplicate it (the tool is bound for guests too)."""
        agent = self._make_agent(enable_long_term_memory=True)
        context = MagicMock(spec=AgentContext)
        context.is_own_team = True

        result = build_system_tools_section(agent, context)
        assert "update_memory" not in result

    def test_excludes_call_agent_from_system_tools_section(self):
        agent = self._make_agent()
        context = MagicMock(spec=AgentContext)
        context.is_own_team = True

        result = build_system_tools_section(agent, context)
        assert "call_agent" not in result

    def test_excludes_post_tools_when_disabled(self):
        agent = self._make_agent(is_post_enabled=False)
        context = MagicMock(spec=AgentContext)
        context.is_own_team = True

        result = build_system_tools_section(agent, context)
        assert "create_post" not in result
        assert "get_post" not in result
        assert "recent_posts" not in result

    def test_excludes_activity_tools_when_disabled(self):
        agent = self._make_agent(is_activity_enabled=False)
        context = MagicMock(spec=AgentContext)
        context.is_own_team = True

        result = build_system_tools_section(agent, context)
        assert "create_activity" not in result
        assert "recent_activities" not in result


def _memory(content: str) -> MagicMock:
    memory = MagicMock()
    memory.content = content
    return memory


class TestBuildSystemPromptMemory:
    @staticmethod
    def _make_agent(enable_long_term_memory) -> MagicMock:
        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "Test"
        agent.ticker = None
        agent.team_id = "team-owner"
        agent.enable_long_term_memory = enable_long_term_memory
        agent.is_activity_enabled = True
        agent.is_post_enabled = True
        agent.tools = None
        agent.telegram_entrypoint_enabled = False
        agent.purpose = None
        agent.personality = None
        agent.principles = None
        agent.prompt = None
        agent.prompt_append = None
        agent.extra_prompt = None
        agent.sub_agents = None
        return agent

    @staticmethod
    def _make_context(**overrides) -> MagicMock:
        context = MagicMock(spec=AgentContext)
        context.agent_id = "agent-1"
        context.is_own_team = overrides.get("is_own_team", True)
        context.is_subagent = overrides.get("is_subagent", False)
        context.entrypoint = overrides.get("entrypoint", AuthorType.WEB)
        context.chat_id = overrides.get("chat_id", "chat-1")
        context.user_id = overrides.get("user_id", None)
        context.team_id = overrides.get("team_id", "team-1")
        return context

    def _config_patch(self):
        return patch(
            "intentkit.core.prompt.config",
            MagicMock(
                intentkit_prompt=None,
                system_prompt=None,
                tg_system_prompt=None,
                xmtp_system_prompt=None,
            ),
        )

    @pytest.fixture(autouse=True)
    def _no_db_lookups(self):
        """These are prompt-shape tests; keep user/task lookups off the DB."""
        with (
            patch(
                "intentkit.core.prompt.User.get",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "intentkit.core.autonomous.get_autonomous_task",
                new=AsyncMock(return_value=None),
            ),
        ):
            yield

    @pytest.mark.asyncio
    async def test_lists_team_and_user_memory(self):
        agent = self._make_agent(enable_long_term_memory=True)
        context = self._make_context(user_id="user-1")
        agent_data = MagicMock()
        agent_data.telegram_id = None

        async def fake_get(agent_id, scope, scope_key):
            if scope == "team":
                assert scope_key == "team-1"
                return _memory("### Facts\n\nUser likes Python.")
            assert (scope, scope_key) == ("user", "user-1")
            return None

        with (
            self._config_patch(),
            patch(
                "intentkit.models.memory.Memory.get",
                new=AsyncMock(side_effect=fake_get),
            ),
        ):
            result = await build_system_prompt(agent, agent_data, context)

        assert "## Memory" in result
        assert "update_memory" in result
        assert "### Team Memory (scope: team)" in result
        assert "User likes Python" in result
        assert "### User Memory (scope: user)" in result
        assert "(empty)" in result

    @pytest.mark.asyncio
    async def test_cron_run_lists_cron_memory(self):
        agent = self._make_agent(enable_long_term_memory=True)
        context = self._make_context(
            entrypoint=AuthorType.TRIGGER, chat_id="autonomous-task-1"
        )
        agent_data = MagicMock()
        agent_data.telegram_id = None

        seen: list[tuple[str, str]] = []

        async def fake_get(agent_id, scope, scope_key):
            seen.append((scope, scope_key))
            return None

        with (
            self._config_patch(),
            patch(
                "intentkit.models.memory.Memory.get",
                new=AsyncMock(side_effect=fake_get),
            ),
        ):
            result = await build_system_prompt(agent, agent_data, context)

        assert "### Cron Task Memory (scope: cron)" in result
        assert ("cron", "task-1") in seen

    @pytest.mark.asyncio
    async def test_subagent_run_has_no_memory_section(self):
        agent = self._make_agent(enable_long_term_memory=True)
        context = self._make_context(is_subagent=True, user_id="user-1")
        agent_data = MagicMock()
        agent_data.telegram_id = None

        with self._config_patch():
            result = await build_system_prompt(agent, agent_data, context)

        assert "## Memory" not in result

    @pytest.mark.asyncio
    async def test_no_memory_section_when_disabled(self):
        agent = self._make_agent(enable_long_term_memory=False)
        context = self._make_context(user_id="user-1")
        agent_data = MagicMock()
        agent_data.telegram_id = None

        with self._config_patch():
            result = await build_system_prompt(agent, agent_data, context)

        assert "## Memory" not in result


class TestSystemToolInstances:
    """Test that system tool singleton instances are correctly initialized."""

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
        context.is_own_team = True

        result = await build_sub_agents_section(agent, context)
        assert result == ""

    @pytest.mark.asyncio
    async def test_sub_agents_section_excluded_when_empty_list(self):
        agent = MagicMock()
        agent.sub_agents = []

        context = MagicMock(spec=AgentContext)
        context.is_own_team = True

        result = await build_sub_agents_section(agent, context)
        assert result == ""

    @pytest.mark.asyncio
    async def test_sub_agents_section_shown_to_guests(self):
        """call_agent is open to guests: delegation grants no extra privileges
        because sub-agent runs recompute their own access context."""
        agent = MagicMock()
        agent.sub_agents = ["helper-bot"]
        agent.sub_agent_prompt = None

        context = MagicMock(spec=AgentContext)
        context.is_own_team = False

        target_agent = MagicMock()
        target_agent.purpose = "Help with tasks"

        with patch(
            "intentkit.core.agent.queries.get_agent_by_id_or_slug",
            new_callable=AsyncMock,
            return_value=target_agent,
        ):
            result = await build_sub_agents_section(agent, context)

        assert "## Sub-Agents" in result
        assert "helper-bot" in result

    @pytest.mark.asyncio
    async def test_sub_agents_section_included_when_configured(self):
        agent = MagicMock()
        agent.sub_agents = ["helper-bot"]
        agent.sub_agent_prompt = None

        target_agent = MagicMock()
        target_agent.purpose = "Help with tasks"

        context = MagicMock(spec=AgentContext)
        context.is_own_team = True

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
        context.is_own_team = True

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
        context.is_own_team = True

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
        agent.tools = None
        agent.telegram_entrypoint_enabled = False
        agent.wallet_id = None
        agent.purpose = None
        agent.personality = None
        agent.principles = None
        agent.prompt = None
        agent.prompt_append = None
        agent.extra_prompt = None
        agent.sub_agents = ["helper-bot"]
        agent.sub_agent_prompt = None

        agent_data = MagicMock()
        agent_data.telegram_id = None

        context = MagicMock(spec=AgentContext)
        context.is_own_team = True
        context.is_subagent = False
        context.entrypoint = AuthorType.WEB
        context.chat_id = "chat-1"
        context.user_id = None
        context.team_id = "team-1"

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


class TestBuildUserInfoSection:
    @pytest.mark.asyncio
    async def test_includes_timezone_and_language(self):
        context = MagicMock(spec=AgentContext)
        context.user_id = "user-1"

        user = MagicMock()
        user.evm_wallet_address = None
        user.email = None
        user.x_username = None
        user.telegram_username = None
        user.timezone = "Asia/Shanghai"
        user.language = "zh-CN"

        with patch(
            "intentkit.core.prompt.User.get",
            new=AsyncMock(return_value=user),
        ):
            result = await _build_user_info_section(context)

        assert "## User Info" in result
        assert "User Timezone: Asia/Shanghai" in result
        assert "User Preferred Language: zh-CN" in result

    @pytest.mark.asyncio
    async def test_omits_locale_lines_when_unset(self):
        context = MagicMock(spec=AgentContext)
        context.user_id = "user-1"

        user = MagicMock()
        user.evm_wallet_address = None
        user.email = "u@example.com"
        user.x_username = None
        user.telegram_username = None
        user.timezone = None
        user.language = None

        with patch(
            "intentkit.core.prompt.User.get",
            new=AsyncMock(return_value=user),
        ):
            result = await _build_user_info_section(context)

        assert "User Timezone" not in result
        assert "User Preferred Language" not in result
        assert "User Email: u@example.com" in result
