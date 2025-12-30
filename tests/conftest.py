"""Pytest configuration and fixtures."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from menu_kit.core.config import Config
from menu_kit.core.database import Database


@pytest.fixture(autouse=True)
def sandbox_environment() -> Generator[Path, None, None]:
    """Sandbox all tests to use a temporary directory for data/config/cache.

    This prevents tests from affecting the real user directories and ensures
    tests are isolated from each other.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox = Path(tmpdir)
        data_dir = sandbox / "data"
        config_dir = sandbox / "config"
        cache_dir = sandbox / "cache"

        # Create the directories
        data_dir.mkdir()
        config_dir.mkdir()
        cache_dir.mkdir()

        with (
            patch("menu_kit.core.config.get_data_dir", return_value=data_dir),
            patch("menu_kit.core.config.get_config_dir", return_value=config_dir),
            patch("menu_kit.core.config.get_cache_dir", return_value=cache_dir),
            # Also patch direct imports in other modules
            patch("menu_kit.plugins.loader.get_data_dir", return_value=data_dir),
            patch("menu_kit.plugins.loader.get_config_dir", return_value=config_dir),
            patch("menu_kit.plugins.builtin.plugins.get_data_dir", return_value=data_dir),
        ):
            yield sandbox


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def disable_notify_send() -> Generator[None, None, None]:
    """Disable notify-send so notifications fall back to print (for capsys capture)."""

    def mock_which(cmd: str) -> str | None:
        if cmd == "notify-send":
            return None
        return cmd

    with patch("shutil.which", side_effect=mock_which):
        yield


@pytest.fixture
def config() -> Config:
    """Create a default config for tests."""
    return Config()


@pytest.fixture
def database(temp_dir: Path) -> Database:
    """Create a test database."""
    return Database(temp_dir / "test.db")
