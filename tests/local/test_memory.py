"""Tests for the local Memory API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intentkit.core.memory import MemoryWithAgent
from intentkit.models.memory import Memory
from intentkit.utils.error import IntentKitAPIError, intentkit_api_error_handler

from app.local.memory import memory_router


def _memory(**overrides) -> MemoryWithAgent:
    now = datetime.now(UTC)
    data = {
        "id": "mem-1",
        "agent_id": "agent-1",
        "scope": "team",
        "scope_key": "system",
        "content": "doc",
        "created_at": now,
        "updated_at": now,
        "agent_name": "Agent 1",
        "agent_picture": None,
    }
    data.update(overrides)
    return MemoryWithAgent.model_validate(data)


@pytest.fixture
def test_client():
    app = FastAPI()
    app.include_router(memory_router)
    _ = app.exception_handler(IntentKitAPIError)(intentkit_api_error_handler)
    return TestClient(app)


def test_list_memories_uses_system_account(test_client):
    with patch(
        "app.local.memory.list_account_memories",
        new=AsyncMock(return_value=[_memory()]),
    ) as mock_list:
        response = test_client.get("/memories")

    assert response.status_code == 200
    mock_list.assert_awaited_once_with("system", "system")
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == "mem-1"
    assert body[0]["agent_name"] == "Agent 1"


def test_update_memory_overwrites_with_system_account(test_client):
    updated = Memory.model_validate(_memory(content="edited").model_dump())
    with patch(
        "app.local.memory.overwrite_memory",
        new=AsyncMock(return_value=updated),
    ) as mock_overwrite:
        response = test_client.put("/memories/mem-1", json={"content": "edited"})

    assert response.status_code == 200
    mock_overwrite.assert_awaited_once_with(
        "mem-1", "edited", team_id="system", user_id="system"
    )
    assert response.json()["content"] == "edited"


def test_update_memory_not_found(test_client):
    with patch(
        "app.local.memory.overwrite_memory",
        new=AsyncMock(
            side_effect=IntentKitAPIError(404, "MemoryNotFound", "Memory not found.")
        ),
    ):
        response = test_client.put("/memories/nope", json={"content": "x"})

    assert response.status_code == 404
