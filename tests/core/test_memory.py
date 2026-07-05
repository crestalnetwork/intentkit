"""Tests for scoped long-term memory: scope resolution, merge, persistence."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from intentkit.abstracts.graph import AgentContext
from intentkit.config.base import Base
from intentkit.core.memory import (
    MAX_MEMORY_BYTES,
    merge_memory_content,
    resolve_memory_scopes,
    update_scoped_memory,
)
from intentkit.models.chat import AuthorType
from intentkit.models.memory import Memory, MemoryTable


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
