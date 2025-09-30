import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.twitter import oauth2_refresh


@pytest.fixture(autouse=True)
def patch_agent_data_save(monkeypatch):
    async def fake_save(self):  # noqa: ANN001
        return None

    monkeypatch.setattr(oauth2_refresh.AgentData, "save", fake_save)


def _build_agent(identifier: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier,
        twitter_refresh_token="refresh-token",
        twitter_access_token=None,
        twitter_access_token_expires_at=None,
    )


@pytest.mark.asyncio
async def test_refresh_token_runs_in_background_thread(monkeypatch):
    agent = _build_agent("agent-1")
    main_thread = threading.get_ident()
    refresh_thread = {}

    def blocking_refresh(refresh_token: str):  # noqa: ANN001
        refresh_thread["id"] = threading.get_ident()
        time.sleep(0.05)
        return {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_at": int(time.time()) + 60,
        }

    monkeypatch.setattr(oauth2_refresh.oauth2_user_handler, "refresh", blocking_refresh)

    await oauth2_refresh.refresh_token(agent)

    assert refresh_thread["id"] != main_thread


@pytest.mark.asyncio
async def test_refresh_expiring_tokens_runs_concurrently(monkeypatch):
    agents = [_build_agent("agent-1"), _build_agent("agent-2")]
    call_count = 0

    def blocking_refresh(refresh_token: str):  # noqa: ANN001
        nonlocal call_count
        call_count += 1
        time.sleep(0.1)
        return {
            "access_token": f"token-{refresh_token}",
            "refresh_token": refresh_token,
            "expires_at": int(time.time()) + 60,
        }

    async def fake_get_expiring_tokens():
        return agents

    monkeypatch.setattr(oauth2_refresh.oauth2_user_handler, "refresh", blocking_refresh)
    monkeypatch.setattr(oauth2_refresh, "get_expiring_tokens", fake_get_expiring_tokens)

    start = time.perf_counter()
    await oauth2_refresh.refresh_expiring_tokens()
    duration = time.perf_counter() - start

    assert call_count == len(agents)
    assert duration < 0.19


@pytest.mark.asyncio
async def test_refresh_token_logs_errors(monkeypatch):
    agent = _build_agent("agent-3")
    error_logger = Mock()

    def failing_refresh(refresh_token: str):  # noqa: ANN001
        raise RuntimeError("refresh failed")

    monkeypatch.setattr(oauth2_refresh.oauth2_user_handler, "refresh", failing_refresh)
    monkeypatch.setattr(oauth2_refresh.logger, "error", error_logger)

    await oauth2_refresh.refresh_token(agent)

    error_logger.assert_called_once()
