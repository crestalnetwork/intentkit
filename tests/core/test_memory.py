"""Tests for scoped long-term memory: scope resolution, merge, persistence."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from intentkit.abstracts.graph import AgentContext
from intentkit.config.base import Base
from intentkit.core.memory import (
    MAX_MEMORY_BYTES,
    list_account_memories,
    merge_memory_content,
    overwrite_memory,
    resolve_memory_scopes,
    update_scoped_memory,
)
from intentkit.models.chat import AuthorType
from intentkit.models.memory import Memory, MemoryTable
from intentkit.utils.error import IntentKitAPIError


@pytest_asyncio.fixture()
async def memory_tables(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[MemoryTable.__table__])
    # The in-process TTL cache outlives the per-test table; clear it so tests
    # never see rows from a previous test's database.
    import intentkit.models.memory as memory_module

    memory_module._memory_cache.clear()
    yield
    memory_module._memory_cache.clear()


def _make_context(**overrides) -> MagicMock:
    context = MagicMock(spec=AgentContext)
    context.agent_id = overrides.get("agent_id", "agent-1")
    context.chat_id = overrides.get("chat_id", "chat-1")
    context.user_id = overrides.get("user_id", "user-1")
    context.team_id = overrides.get("team_id", "team-1")
    context.entrypoint = overrides.get("entrypoint", AuthorType.WEB)
    context.is_subagent = overrides.get("is_subagent", False)
    context.is_own_team = overrides.get("is_own_team", True)
    return context


def _make_agent(team_id: str | None = "team-owner") -> MagicMock:
    agent = MagicMock()
    agent.team_id = team_id
    return agent


class TestResolveMemoryScopes:
    def test_subagent_has_no_memory(self):
        context = _make_context(is_subagent=True)
        assert resolve_memory_scopes(_make_agent(), context) == []

    def test_web_user_gets_team_and_user(self):
        context = _make_context(entrypoint=AuthorType.WEB, user_id="user-9")
        scopes = resolve_memory_scopes(_make_agent(), context)
        assert [(s.scope, s.scope_key) for s in scopes] == [
            ("team", "team-1"),
            ("user", "user-9"),
        ]

    def test_consuming_team_wins_over_owning_team(self):
        """A public agent visited by another team loads the visitor's memory."""
        context = _make_context(team_id="team-visitor")
        scopes = resolve_memory_scopes(_make_agent(team_id="team-owner"), context)
        assert scopes[0].scope_key == "team-visitor"

    def test_own_team_falls_back_to_owner_then_system(self):
        context = _make_context(team_id=None, is_own_team=True)
        scopes = resolve_memory_scopes(_make_agent(team_id="team-owner"), context)
        assert scopes[0].scope_key == "team-owner"

        scopes = resolve_memory_scopes(_make_agent(team_id=None), context)
        assert scopes[0].scope_key == "system"

    def test_teamless_guest_gets_no_team_scope(self):
        """A guest without a team must never see the owning team's memory."""
        context = _make_context(team_id=None, is_own_team=False, user_id="user-9")
        scopes = resolve_memory_scopes(_make_agent(team_id="team-owner"), context)
        assert [(s.scope, s.scope_key) for s in scopes] == [("user", "user-9")]

    def test_trigger_gets_cron_scope_keyed_by_task_id(self):
        context = _make_context(
            entrypoint=AuthorType.TRIGGER, chat_id="autonomous-task-42"
        )
        scopes = resolve_memory_scopes(_make_agent(), context)
        assert [(s.scope, s.scope_key) for s in scopes] == [
            ("team", "team-1"),
            ("cron", "task-42"),
        ]

    @pytest.mark.parametrize(
        "entrypoint",
        [
            AuthorType.TELEGRAM,
            AuthorType.SLACK,
            AuthorType.LARK,
            AuthorType.WECHAT,
            AuthorType.DISCORD,
        ],
    )
    def test_channel_entrypoints_get_channel_scope(self, entrypoint):
        context = _make_context(entrypoint=entrypoint, chat_id="thread-7")
        scopes = resolve_memory_scopes(_make_agent(), context)
        assert ("channel", "thread-7") in [(s.scope, s.scope_key) for s in scopes]
        assert all(s.scope != "user" for s in scopes)

    def test_anonymous_web_gets_team_only(self):
        context = _make_context(user_id=None)
        scopes = resolve_memory_scopes(_make_agent(), context)
        assert [s.scope for s in scopes] == ["team"]


class TestMergeMemoryContent:
    @pytest.fixture
    def mock_llm(self):
        mock_model = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "#### Merged Memory\n\nConsolidated info here."
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        mock_llm_model = AsyncMock()
        mock_llm_model.create_instance = AsyncMock(return_value=mock_model)
        return mock_llm_model, mock_model

    def _patches(self, mock_llm_model):
        return (
            patch(
                "intentkit.models.llm_picker.pick_summarize_model",
                return_value="test-model",
            ),
            patch(
                "intentkit.models.llm.create_llm_model",
                new_callable=AsyncMock,
                return_value=mock_llm_model,
            ),
        )

    @pytest.mark.asyncio
    async def test_new_memory_without_existing(self, mock_llm):
        mock_llm_model, mock_model = mock_llm
        p1, p2 = self._patches(mock_llm_model)
        with p1, p2:
            result = await merge_memory_content("", "User likes cats")

        assert result == "#### Merged Memory\n\nConsolidated info here."
        user_msg = mock_model.ainvoke.call_args[0][0][1].content
        assert "### New Information" in user_msg
        assert "### Existing Memory" not in user_msg

    @pytest.mark.asyncio
    async def test_merges_with_existing(self, mock_llm):
        mock_llm_model, mock_model = mock_llm
        p1, p2 = self._patches(mock_llm_model)
        with p1, p2:
            await merge_memory_content("User likes dogs.", "User also likes cats")

        user_msg = mock_model.ainvoke.call_args[0][0][1].content
        assert "### Existing Memory" in user_msg
        assert "User likes dogs" in user_msg
        assert "User also likes cats" in user_msg

    @pytest.mark.asyncio
    async def test_truncates_to_max_bytes(self, mock_llm):
        mock_llm_model, mock_model = mock_llm
        mock_response = MagicMock()
        mock_response.content = "x" * (MAX_MEMORY_BYTES + 1000)
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        p1, p2 = self._patches(mock_llm_model)
        with p1, p2:
            result = await merge_memory_content("", "new content")

        assert len(result.encode("utf-8")) <= MAX_MEMORY_BYTES

    @pytest.mark.asyncio
    async def test_fallback_on_llm_failure(self):
        mock_llm_model = AsyncMock()
        mock_llm_model.create_instance = AsyncMock(
            side_effect=Exception("LLM unavailable")
        )
        p1, p2 = self._patches(mock_llm_model)
        with p1, p2:
            result = await merge_memory_content("existing memory", "new info")

        assert "existing memory" in result
        assert "new info" in result

    @pytest.mark.asyncio
    async def test_handles_non_string_llm_response(self, mock_llm):
        mock_llm_model, mock_model = mock_llm
        mock_response = MagicMock()
        mock_response.content = ["some", "list"]
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        p1, p2 = self._patches(mock_llm_model)
        with p1, p2:
            result = await merge_memory_content("", "new content")

        assert isinstance(result, str)


class TestMemoryPersistence:
    @pytest.mark.asyncio
    async def test_upsert_insert_and_replace(self, memory_tables):
        created = await Memory.upsert("agent-1", "team", "team-1", "v1")
        assert created.content == "v1"

        replaced = await Memory.upsert("agent-1", "team", "team-1", "v2")
        assert replaced.id == created.id
        assert replaced.content == "v2"

        fetched = await Memory.get("agent-1", "team", "team-1")
        assert fetched is not None and fetched.content == "v2"

    @pytest.mark.asyncio
    async def test_scope_rows_are_independent(self, memory_tables):
        await Memory.upsert("agent-1", "team", "team-1", "team doc")
        await Memory.upsert("agent-1", "user", "user-1", "user doc")
        await Memory.upsert("agent-2", "team", "team-1", "other agent")

        team = await Memory.get("agent-1", "team", "team-1")
        user = await Memory.get("agent-1", "user", "user-1")
        assert team is not None and team.content == "team doc"
        assert user is not None and user.content == "user doc"
        assert await Memory.get("agent-1", "user", "user-2") is None

    @pytest.mark.asyncio
    async def test_update_scoped_memory_merges_and_persists(self, memory_tables):
        with patch(
            "intentkit.core.memory.merge_memory_content",
            new=AsyncMock(return_value="merged doc"),
        ) as mock_merge:
            result = await update_scoped_memory("agent-1", "user", "user-1", "new")

        assert result == "merged doc"
        mock_merge.assert_awaited_once_with("", "new")
        stored = await Memory.get("agent-1", "user", "user-1")
        assert stored is not None and stored.content == "merged doc"


class TestAccountMemoryManagement:
    """Management-API helpers: list an account's memories, overwrite one."""

    @pytest.fixture(autouse=True)
    def _no_agent_info_lookups(self, monkeypatch):
        """Agent-info enrichment needs Redis and the lead-name fallback needs
        the teams table; stub both out."""

        async def fake_get_agent_infos(agent_ids):
            return {}

        async def fake_lead_config(team_id):
            return None

        monkeypatch.setattr(
            "intentkit.core.agent.info.get_agent_infos", fake_get_agent_infos
        )
        monkeypatch.setattr(
            "intentkit.models.team.Team.get_lead_agent_config", fake_lead_config
        )

    @pytest.mark.asyncio
    async def test_list_returns_only_own_team_and_user_rows(self, memory_tables):
        await Memory.upsert("agent-1", "team", "team-1", "team doc")
        await Memory.upsert("team-team-1", "team", "team-1", "lead doc")
        await Memory.upsert("agent-1", "user", "user-1", "user doc")
        # None of these belong to (team-1, user-1):
        await Memory.upsert("agent-1", "team", "team-2", "other team")
        await Memory.upsert("agent-1", "user", "user-2", "other user")
        await Memory.upsert("agent-1", "channel", "chat-1", "channel doc")
        await Memory.upsert("agent-1", "cron", "task-1", "cron doc")

        memories = await list_account_memories("team-1", "user-1")

        assert {(m.scope, m.agent_id, m.content) for m in memories} == {
            ("team", "agent-1", "team doc"),
            ("team", "team-team-1", "lead doc"),
            ("user", "agent-1", "user doc"),
        }
        # Team scope sorts before user scope for stable section grouping.
        assert [m.scope for m in memories] == ["team", "team", "user"]

    @pytest.mark.asyncio
    async def test_list_labels_lead_agent(self, memory_tables):
        await Memory.upsert("team-team-1", "team", "team-1", "lead doc")
        await Memory.upsert("agent-1", "team", "team-1", "team doc")

        with patch(
            "intentkit.models.team.Team.get_lead_agent_config",
            new=AsyncMock(return_value={"name": "Concierge", "avatar": "lead.png"}),
        ):
            memories = await list_account_memories("team-1", "user-1")

        by_agent = {m.agent_id: m for m in memories}
        assert by_agent["team-team-1"].agent_name == "Concierge"
        assert by_agent["team-team-1"].agent_picture == "lead.png"
        assert by_agent["agent-1"].agent_name is None

    @pytest.mark.asyncio
    async def test_list_lead_agent_default_name(self, memory_tables):
        await Memory.upsert("team-team-1", "team", "team-1", "lead doc")

        with patch(
            "intentkit.models.team.Team.get_lead_agent_config",
            new=AsyncMock(return_value=None),
        ):
            memories = await list_account_memories("team-1", "user-1")

        assert memories[0].agent_name == "Team Lead"

    @pytest.mark.asyncio
    async def test_overwrite_own_rows_verbatim(self, memory_tables):
        team_row = await Memory.upsert("agent-1", "team", "team-1", "team doc")
        user_row = await Memory.upsert("agent-1", "user", "user-1", "user doc")

        updated = await overwrite_memory(
            team_row.id, "edited team", team_id="team-1", user_id="user-1"
        )
        assert updated.content == "edited team"

        updated = await overwrite_memory(
            user_row.id, "edited user", team_id="team-1", user_id="user-1"
        )
        assert updated.content == "edited user"

        stored = await Memory.get("agent-1", "team", "team-1")
        assert stored is not None and stored.content == "edited team"

    @pytest.mark.asyncio
    async def test_overwrite_rejects_foreign_and_missing_rows(self, memory_tables):
        foreign_user = await Memory.upsert("agent-1", "user", "user-2", "not yours")
        foreign_team = await Memory.upsert("agent-1", "team", "team-2", "not yours")
        channel_row = await Memory.upsert("agent-1", "channel", "chat-1", "internal")

        for memory_id in (foreign_user.id, foreign_team.id, channel_row.id, "nope"):
            with pytest.raises(IntentKitAPIError) as exc:
                await overwrite_memory(
                    memory_id, "x", team_id="team-1", user_id="user-1"
                )
            assert exc.value.status_code == 404

        stored = await Memory.get("agent-1", "user", "user-2")
        assert stored is not None and stored.content == "not yours"

    @pytest.mark.asyncio
    async def test_overwrite_enforces_byte_limit(self, memory_tables):
        row = await Memory.upsert("agent-1", "user", "user-1", "doc")

        with pytest.raises(IntentKitAPIError) as exc:
            await overwrite_memory(
                row.id,
                "x" * (MAX_MEMORY_BYTES + 1),
                team_id="team-1",
                user_id="user-1",
            )
        assert exc.value.status_code == 422

        stored = await Memory.get("agent-1", "user", "user-1")
        assert stored is not None and stored.content == "doc"


class _FakeRequest:
    """Minimal stand-in for ModelRequest: runtime.context plus override()."""

    def __init__(self, context: AgentContext) -> None:
        self.runtime = SimpleNamespace(context=context)
        self.overridden: dict[str, Any] = {}

    def override(self, **kwargs: Any) -> "_FakeRequest":
        self.overridden.update(kwargs)
        return self


class TestUpdateMemoryToolGating:
    """ToolBindingMiddleware binds update_memory only when a scope resolves."""

    @staticmethod
    async def _bound_tool_names(context: AgentContext) -> set[str]:
        from intentkit.core.middleware import ToolBindingMiddleware
        from intentkit.core.system_tools import current_time, update_memory

        llm_model = MagicMock()
        llm_model.create_instance = AsyncMock(return_value=MagicMock())
        middleware = ToolBindingMiddleware(llm_model, [current_time, update_memory])
        request = _FakeRequest(context)
        handler = AsyncMock(return_value="response")
        await middleware.awrap_model_call(cast(Any, request), handler)
        return {t.name for t in request.overridden["tools"]}

    @staticmethod
    def _agent_context(**overrides) -> AgentContext:
        agent = MagicMock()
        agent.team_id = overrides.pop("agent_team_id", "team-owner")
        defaults: dict[str, Any] = {
            "agent_id": "agent-1",
            "get_agent": lambda: agent,
            "chat_id": "chat-1",
            "user_id": "user-1",
            "team_id": "team-1",
            "entrypoint": AuthorType.WEB,
            "is_own_team": True,
        }
        defaults.update(overrides)
        return AgentContext(**defaults)

    @pytest.mark.asyncio
    async def test_bound_when_scopes_resolve(self):
        names = await self._bound_tool_names(self._agent_context())
        assert "update_memory" in names

    @pytest.mark.asyncio
    async def test_dropped_for_subagent_runs(self):
        names = await self._bound_tool_names(self._agent_context(call_depth=1))
        assert "update_memory" not in names
        assert "current_time" in names

    @pytest.mark.asyncio
    async def test_dropped_for_teamless_anonymous_guests(self):
        context = self._agent_context(user_id=None, team_id=None, is_own_team=False)
        names = await self._bound_tool_names(context)
        assert "update_memory" not in names
        assert "current_time" in names
