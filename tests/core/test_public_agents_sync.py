"""Tests for public agents sync mechanism."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_sync_skips_when_no_directory():
    """Sync should skip when public_agents directory doesn't exist."""
    from intentkit.core.public_agents import sync_public_agents

    with patch("intentkit.core.public_agents.PUBLIC_AGENTS_DIR") as mock_dir:
        mock_dir.exists.return_value = False
        await sync_public_agents()
        # Should not raise, just return


@pytest.mark.asyncio
async def test_sync_skips_when_no_yaml_files():
    """Sync should skip when no YAML files exist."""
    from intentkit.core.public_agents import sync_public_agents

    with patch("intentkit.core.public_agents.PUBLIC_AGENTS_DIR") as mock_dir:
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = []
        await sync_public_agents()
        # Should not raise


@pytest.mark.asyncio
async def test_ensure_prerequisites_creates_teams():
    """Prerequisites function should create predefined and public teams."""
    from intentkit.core.public_agents import ensure_public_agent_prerequisites

    mock_session = AsyncMock()
    # All get calls return None (nothing exists yet)
    mock_session.get.return_value = None

    with patch("intentkit.core.public_agents.get_session") as mock_get_session:
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

        await ensure_public_agent_prerequisites()

    # Should have added 4 items: predefined user, predefined team,
    # predefined membership, public team
    assert mock_session.add.call_count == 4
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_prerequisites_skips_existing():
    """Prerequisites should skip creation if entities already exist."""
    from intentkit.core.public_agents import ensure_public_agent_prerequisites

    mock_session = AsyncMock()
    # All entities already exist
    mock_session.get.return_value = MagicMock()

    with patch("intentkit.core.public_agents.get_session") as mock_get_session:
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

        await ensure_public_agent_prerequisites()

    # Should not add anything
    mock_session.add.assert_not_called()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_prerequisites_handles_error():
    """Prerequisites should handle errors gracefully."""
    from intentkit.core.public_agents import ensure_public_agent_prerequisites

    with patch("intentkit.core.public_agents.get_session") as mock_get_session:
        mock_get_session.return_value.__aenter__ = AsyncMock(
            side_effect=Exception("DB error")
        )
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

        # Should not raise
        await ensure_public_agent_prerequisites()


@pytest.mark.asyncio
async def test_sync_uses_predefined_owner():
    """Synced agents should use owner='predefined' and team_id='predefined'."""
    from intentkit.core.public_agents import OWNER, TEAM_ID

    assert OWNER == "predefined"
    assert TEAM_ID == "predefined"
