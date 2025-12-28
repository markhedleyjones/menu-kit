"""Pytest configuration and fixtures."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from menu_kit.core.config import Config
from menu_kit.core.database import Database


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config() -> Config:
    """Create a default config for tests."""
    return Config()


@pytest.fixture
def database(temp_dir: Path) -> Database:
    """Create a test database."""
    return Database(temp_dir / "test.db")
