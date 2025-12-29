"""Pytest configuration and fixtures."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from menu_kit.core.config import Config
from menu_kit.core.database import Database


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
