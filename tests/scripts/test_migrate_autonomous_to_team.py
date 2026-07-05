"""Unit tests for the autonomous -> team migration row builder."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def load_script_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "migrate_autonomous_to_team.py"
    )
    spec = spec_from_file_location("migrate_autonomous_to_team", script_path)
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load script module")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_rows_sets_team_and_target_agent():
    build_task_rows = load_script_module().build_task_rows
    agent_rows = [
        (
            "agent-1",
            "team-1",
            [{"id": "t1", "cron": "*/5 * * * *", "prompt": "do", "enabled": True}],
        )
    ]
    rows, stats = build_task_rows(agent_rows)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "t1"
    assert row["team_id"] == "team-1"
    assert row["target_agent_id"] == "agent-1"
    assert row["cron"] == "*/5 * * * *"
    assert stats["migrated"] == 1


def test_build_rows_converts_minutes_to_cron():
    build_task_rows = load_script_module().build_task_rows
    agent_rows = [
        ("agent-1", "team-1", [{"id": "t1", "minutes": 5, "prompt": "do"}]),
    ]
    rows, _stats = build_task_rows(agent_rows)
    assert rows[0]["cron"] == "*/5 * * * *"


def test_build_rows_converts_zero_minutes_to_default_cron():
    # minutes=0 must still convert (old behavior normalized it), not be dropped.
    build_task_rows = load_script_module().build_task_rows
    agent_rows = [
        ("agent-1", "team-1", [{"id": "t1", "minutes": 0, "prompt": "do"}]),
    ]
    rows, stats = build_task_rows(agent_rows)
    assert len(rows) == 1
    assert rows[0]["cron"] == "*/5 * * * *"
    assert stats["migrated"] == 1


def test_build_rows_skips_agent_without_team():
    build_task_rows = load_script_module().build_task_rows
    agent_rows = [
        ("agent-1", None, [{"id": "t1", "cron": "*/5 * * * *", "prompt": "do"}]),
    ]
    rows, stats = build_task_rows(agent_rows)
    assert rows == []
    assert stats["skipped_no_team"] == 1


def test_build_rows_skips_task_without_schedule():
    build_task_rows = load_script_module().build_task_rows
    agent_rows = [
        ("agent-1", "team-1", [{"id": "t1", "prompt": "do"}]),
    ]
    rows, stats = build_task_rows(agent_rows)
    assert rows == []
    assert stats["skipped_no_cron"] == 1


def test_build_rows_preserves_runtime():
    build_task_rows = load_script_module().build_task_rows
    agent_rows = [
        (
            "agent-1",
            "team-1",
            [
                {
                    "id": "t1",
                    "cron": "0 9 * * *",
                    "prompt": "do",
                    "status": "waiting",
                }
            ],
        )
    ]
    rows, _stats = build_task_rows(agent_rows)
    assert rows[0]["status"] == "waiting"


def _patch_module_session(module, first_row):
    """Patch the loaded module's get_session to a mocked async session.

    Returns the started patcher so the caller can stop it; the session's only
    job is to make ``SELECT id FROM autonomous_tasks LIMIT 1`` return first_row.
    """
    mock_session = MagicMock()
    result = MagicMock()
    result.first.return_value = first_row
    mock_session.execute = AsyncMock(return_value=result)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    patcher = patch.object(module, "get_session", return_value=ctx)
    patcher.start()
    return patcher


@pytest.mark.asyncio
async def test_migrate_if_table_empty_skips_when_populated():
    module = load_script_module()
    patcher = _patch_module_session(module, first_row=("task-1",))
    migrate_mock = AsyncMock()
    try:
        with patch.object(module, "migrate", migrate_mock):
            ran = await module.migrate_if_table_empty()
        assert ran is False
        migrate_mock.assert_not_awaited()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_migrate_if_table_empty_runs_when_empty():
    module = load_script_module()
    patcher = _patch_module_session(module, first_row=None)
    migrate_mock = AsyncMock()
    try:
        with patch.object(module, "migrate", migrate_mock):
            ran = await module.migrate_if_table_empty()
        assert ran is True
        migrate_mock.assert_awaited_once()
    finally:
        patcher.stop()


def test_build_rows_tolerates_malformed_minutes():
    # Legacy JSONB is schema-less; a bad minutes value must skip the task,
    # not fail the whole batch.
    build_task_rows = load_script_module().build_task_rows
    agent_rows = [
        ("agent-1", "team-1", [{"id": "t1", "minutes": "abc", "prompt": "do"}]),
    ]
    rows, stats = build_task_rows(agent_rows)
    assert rows == []
    assert stats["skipped_no_cron"] == 1
