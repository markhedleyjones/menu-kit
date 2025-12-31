"""Tests for display mode functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from menu_kit.core.config import Config
from menu_kit.core.database import Database, MenuItem
from menu_kit.core.display_mode import (
    CORE_PLUGIN_NAME,
    DISPLAY_MODES_KEY,
    DisplayMode,
    DisplayModeManager,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temp directory for tests."""
    return tmp_path


class TestDisplayModeManager:
    """Tests for DisplayModeManager."""

    def test_default_mode_inline_below_threshold(self, temp_dir: Path) -> None:
        """Plugins with items below threshold default to inline mode."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        # Add 5 items (below default threshold of 20)
        items = [MenuItem(id=f"test:{i}", title=f"Item {i}", plugin="testplugin") for i in range(5)]
        database.add_items(items)

        mode = manager.get_mode("testplugin")
        assert mode == DisplayMode.INLINE

    def test_default_mode_submenu_above_threshold(self, temp_dir: Path) -> None:
        """Plugins with items above threshold default to submenu mode."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        # Add 25 items (above default threshold of 20)
        items = [
            MenuItem(id=f"test:{i}", title=f"Item {i}", plugin="testplugin") for i in range(25)
        ]
        database.add_items(items)

        mode = manager.get_mode("testplugin")
        assert mode == DisplayMode.SUBMENU

    def test_explicit_mode_overrides_default(self, temp_dir: Path) -> None:
        """Explicit mode setting overrides auto-detection."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        # Add 25 items (would default to submenu)
        items = [
            MenuItem(id=f"test:{i}", title=f"Item {i}", plugin="testplugin") for i in range(25)
        ]
        database.add_items(items)

        # Set explicit mode to inline
        manager.set_mode("testplugin", DisplayMode.INLINE)

        mode = manager.get_mode("testplugin")
        assert mode == DisplayMode.INLINE

    def test_mode_persistence(self, temp_dir: Path) -> None:
        """Mode settings persist across manager instances."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")

        # Set mode with first manager
        manager1 = DisplayModeManager(config, database)
        manager1.set_mode("testplugin", DisplayMode.SUBMENU)

        # Create new manager and verify mode is persisted
        manager2 = DisplayModeManager(config, database)
        mode = manager2.get_mode("testplugin")
        assert mode == DisplayMode.SUBMENU

    def test_mode_stored_in_database(self, temp_dir: Path) -> None:
        """Mode is stored in plugin_data table."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        manager.set_mode("testplugin", DisplayMode.INLINE)

        # Check database directly
        stored = database.get_plugin_data(CORE_PLUGIN_NAME, DISPLAY_MODES_KEY)
        assert stored is not None
        assert stored["testplugin"] == "inline"

    def test_format_inline_title(self, temp_dir: Path) -> None:
        """Inline title is formatted with plugin prefix."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        formatted = manager.format_inline_title("files", "document.pdf")
        assert formatted == "Files: document.pdf"

    def test_format_inline_title_preserves_case(self, temp_dir: Path) -> None:
        """Original title case is preserved, only prefix is titlecased."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        formatted = manager.format_inline_title("apps", "Firefox")
        assert formatted == "Apps: Firefox"

    def test_cache_invalidation_on_set(self, temp_dir: Path) -> None:
        """Cache is invalidated when mode is set."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        # Add items to trigger auto mode
        items = [MenuItem(id=f"test:{i}", title=f"Item {i}", plugin="testplugin") for i in range(5)]
        database.add_items(items)

        # Get mode to populate cache
        mode1 = manager.get_mode("testplugin")
        assert mode1 == DisplayMode.INLINE

        # Set explicit mode
        manager.set_mode("testplugin", DisplayMode.SUBMENU)

        # Should reflect new mode immediately
        mode2 = manager.get_mode("testplugin")
        assert mode2 == DisplayMode.SUBMENU


class TestDisplayModeConfig:
    """Tests for display mode configuration."""

    def test_config_default_display_mode_inline(self, temp_dir: Path) -> None:
        """When config sets default to inline, all plugins are inline."""
        config_path = temp_dir / "config.toml"
        config_path.write_text('[plugins]\ndefault_display_mode = "inline"\n')
        config = Config.load(config_path)
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        # Add many items (would be submenu in auto mode)
        items = [
            MenuItem(id=f"test:{i}", title=f"Item {i}", plugin="testplugin") for i in range(50)
        ]
        database.add_items(items)

        mode = manager.get_mode("testplugin")
        assert mode == DisplayMode.INLINE

    def test_config_default_display_mode_submenu(self, temp_dir: Path) -> None:
        """When config sets default to submenu, all plugins are submenu."""
        config_path = temp_dir / "config.toml"
        config_path.write_text('[plugins]\ndefault_display_mode = "submenu"\n')
        config = Config.load(config_path)
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        # Add few items (would be inline in auto mode)
        items = [MenuItem(id=f"test:{i}", title=f"Item {i}", plugin="testplugin") for i in range(3)]
        database.add_items(items)

        mode = manager.get_mode("testplugin")
        assert mode == DisplayMode.SUBMENU

    def test_config_item_threshold(self, temp_dir: Path) -> None:
        """Custom threshold is respected in auto mode."""
        config_path = temp_dir / "config.toml"
        config_path.write_text("[plugins]\nitem_threshold = 10\n")
        config = Config.load(config_path)
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        # Add 15 items (above custom threshold of 10)
        items = [
            MenuItem(id=f"test:{i}", title=f"Item {i}", plugin="testplugin") for i in range(15)
        ]
        database.add_items(items)

        mode = manager.get_mode("testplugin")
        assert mode == DisplayMode.SUBMENU


class TestDisplayModeEdgeCases:
    """Tests for edge cases in display mode handling."""

    def test_unknown_plugin_defaults_to_inline(self, temp_dir: Path) -> None:
        """Plugin with no items defaults to inline."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        mode = manager.get_mode("nonexistent")
        assert mode == DisplayMode.INLINE

    def test_multiple_plugins_independent(self, temp_dir: Path) -> None:
        """Each plugin has independent mode settings."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        manager.set_mode("plugin_a", DisplayMode.INLINE)
        manager.set_mode("plugin_b", DisplayMode.SUBMENU)

        assert manager.get_mode("plugin_a") == DisplayMode.INLINE
        assert manager.get_mode("plugin_b") == DisplayMode.SUBMENU

    def test_boundary_at_threshold(self, temp_dir: Path) -> None:
        """Exactly at threshold stays inline (> not >=)."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        # Add exactly 20 items (at default threshold)
        items = [
            MenuItem(id=f"test:{i}", title=f"Item {i}", plugin="testplugin") for i in range(20)
        ]
        database.add_items(items)

        mode = manager.get_mode("testplugin")
        assert mode == DisplayMode.INLINE

    def test_one_over_threshold(self, temp_dir: Path) -> None:
        """One over threshold switches to submenu."""
        config = Config.load(temp_dir / "config.toml")
        database = Database(temp_dir / "test.db")
        manager = DisplayModeManager(config, database)

        # Add exactly 21 items (one over default threshold)
        items = [
            MenuItem(id=f"test:{i}", title=f"Item {i}", plugin="testplugin") for i in range(21)
        ]
        database.add_items(items)

        mode = manager.get_mode("testplugin")
        assert mode == DisplayMode.SUBMENU
