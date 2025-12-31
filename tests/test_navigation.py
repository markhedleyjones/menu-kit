"""Tests for menu navigation structure.

These tests verify the complete navigation tree of the default menu,
ensuring all paths lead to expected destinations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from menu_kit.core.config import Config
from menu_kit.core.database import Database, MenuItem
from menu_kit.menu.base import MenuBackend, MenuResult
from menu_kit.plugins.base import Plugin, PluginContext
from menu_kit.plugins.builtin.plugins import PluginsPlugin
from menu_kit.plugins.builtin.settings import SettingsPlugin

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class MenuCapture:
    """Captures what was shown in a menu call."""

    items: list[MenuItem]
    prompt: str


@dataclass
class MockBackend(MenuBackend):
    """Mock backend that records shown menus and returns scripted selections."""

    selections: list[str | None] = field(default_factory=list)
    captures: list[MenuCapture] = field(default_factory=list)
    _selection_index: int = 0

    @property
    def name(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return True

    def show(
        self,
        items: list[MenuItem],
        prompt: str = "",
        extra_args: list[str] | None = None,
    ) -> MenuResult:
        """Record the menu and return next scripted selection."""
        self.captures.append(MenuCapture(items=list(items), prompt=prompt))

        if self._selection_index >= len(self.selections):
            return MenuResult(cancelled=True, selected=None)

        selection_id = self.selections[self._selection_index]
        self._selection_index += 1

        if selection_id is None:
            return MenuResult(cancelled=False, selected=None)

        # Find the item by ID (handle back button)
        for item in items:
            if item.id == selection_id:
                return MenuResult(cancelled=False, selected=item)

        # Selection not found - treat as cancel
        return MenuResult(cancelled=True, selected=None)


class MockLoader:
    """Mock plugin loader for testing."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def get_all_plugins(self) -> dict[str, Plugin]:
        return self._plugins

    def register(self, plugin: Plugin) -> None:
        self._plugins[plugin.info.name] = plugin

    def index_all(self) -> None:
        """Mock index_all - does nothing in tests."""


def create_context(
    temp_dir: Path, selections: list[str | None]
) -> tuple[PluginContext, MockBackend]:
    """Create a plugin context with a mock backend."""
    config = Config.load(temp_dir / "config.toml")
    database = Database(temp_dir / "test.db")
    backend = MockBackend(selections=selections)
    ctx = PluginContext(config=config, database=database, menu_backend=backend)

    # Set up mock loader with bundled plugins
    loader = MockLoader()
    loader.register(SettingsPlugin())
    loader.register(PluginsPlugin())
    ctx._loader = loader  # type: ignore[attr-defined]

    return ctx, backend


class TestMainMenuStructure:
    """Tests for the main menu items registered by built-in plugins."""

    def test_settings_registers_submenu(self, temp_dir: Path) -> None:
        """Settings plugin registers a submenu item in main menu."""
        ctx, _ = create_context(temp_dir, [])
        plugin = SettingsPlugin()

        items = plugin.index(ctx)

        assert len(items) == 1
        assert items[0].id == "settings"
        assert items[0].title == "Settings"
        assert items[0].plugin == "settings"

    def test_plugins_registers_submenu(self, temp_dir: Path) -> None:
        """Plugins plugin registers a submenu item in main menu."""
        ctx, _ = create_context(temp_dir, [])
        plugin = PluginsPlugin()

        items = plugin.index(ctx)

        assert len(items) == 1
        assert items[0].id == "plugins"
        assert items[0].title == "Plugins"
        assert items[0].plugin == "plugins"


class TestSettingsNavigation:
    """Tests for navigation within the Settings plugin."""

    def test_settings_menu_items(self, temp_dir: Path) -> None:
        """Settings menu shows expected items."""
        ctx, backend = create_context(temp_dir, ["_back"])
        plugin = SettingsPlugin()

        plugin.run(ctx)

        assert len(backend.captures) == 1
        menu = backend.captures[0]
        assert menu.prompt == "Settings"

        item_ids = [item.id for item in menu.items]
        assert "_back" in item_ids
        assert "settings:frequency" in item_ids
        assert "settings:backend" in item_ids
        assert "settings:rebuild" in item_ids

    def test_settings_frequency_action(self, temp_dir: Path) -> None:
        """Selecting frequency tracking shows notification and returns to settings."""
        ctx, backend = create_context(temp_dir, ["settings:frequency", "_back"])
        plugin = SettingsPlugin()

        plugin.run(ctx)

        # Should show settings menu twice (once before action, once after)
        assert len(backend.captures) == 2
        assert backend.captures[0].prompt == "Settings"
        assert backend.captures[1].prompt == "Settings"

    def test_settings_back_exits(self, temp_dir: Path) -> None:
        """Selecting back from settings exits the plugin."""
        ctx, backend = create_context(temp_dir, ["_back"])
        plugin = SettingsPlugin()

        plugin.run(ctx)

        assert len(backend.captures) == 1


class TestPluginsNavigation:
    """Tests for navigation within the Plugins plugin."""

    def test_plugins_main_menu_items(self, temp_dir: Path) -> None:
        """Plugins main menu shows expected items."""
        ctx, backend = create_context(temp_dir, ["_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        assert len(backend.captures) == 1
        menu = backend.captures[0]
        assert menu.prompt == "Plugins"

        item_ids = [item.id for item in menu.items]
        assert "_back" in item_ids
        assert "plugins:installed" in item_ids
        assert "plugins:browse" in item_ids
        assert "plugins:updates" in item_ids

    def test_plugins_installed_menu(self, temp_dir: Path) -> None:
        """Navigating to Installed shows installed plugins."""
        ctx, backend = create_context(temp_dir, ["plugins:installed", "_back", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        assert len(backend.captures) == 3

        # First menu: Plugins main
        assert backend.captures[0].prompt == "Plugins"

        # Second menu: Installed Plugins
        installed_menu = backend.captures[1]
        assert installed_menu.prompt == "Installed Plugins"
        item_ids = [item.id for item in installed_menu.items]
        assert "_back" in item_ids
        assert "plugins:info:settings" in item_ids
        assert "plugins:info:plugins" in item_ids

        # Third menu: Back to Plugins main
        assert backend.captures[2].prompt == "Plugins"

    def test_plugins_browse_menu(self, temp_dir: Path) -> None:
        """Navigating to Browse skips to repo plugins when only one repo configured."""
        ctx, backend = create_context(temp_dir, ["plugins:browse", "_back", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        # With one repo, skips directly to showing repo plugins
        prompts = [c.prompt for c in backend.captures]
        assert prompts == ["Plugins", "Official", "Plugins"]

    def test_plugins_deep_navigation(self, temp_dir: Path) -> None:
        """Test deep navigation: Plugins → Installed → plugin options → back → back → back."""
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:installed",  # Go to Installed
                "plugins:info:settings",  # Select settings plugin (shows options)
                "_back",  # Back to Installed
                "_back",  # Back to Plugins main
                "_back",  # Exit plugin
            ],
        )
        plugin = PluginsPlugin()

        plugin.run(ctx)

        prompts = [c.prompt for c in backend.captures]
        assert prompts == [
            "Plugins",
            "Installed Plugins",
            "Settings",  # Plugin options menu
            "Installed Plugins",  # After back from options
            "Plugins",  # After back from Installed
        ]

    def test_plugins_back_from_each_level(self, temp_dir: Path) -> None:
        """Verify back button works at each navigation level."""
        # Test: Plugins → back (should exit)
        ctx, backend = create_context(temp_dir, ["_back"])
        plugin = PluginsPlugin()
        plugin.run(ctx)
        assert len(backend.captures) == 1
        assert backend.captures[0].prompt == "Plugins"

        # Test: Plugins → Installed → back → back
        ctx, backend = create_context(temp_dir, ["plugins:installed", "_back", "_back"])
        plugin = PluginsPlugin()
        plugin.run(ctx)
        prompts = [c.prompt for c in backend.captures]
        assert prompts == ["Plugins", "Installed Plugins", "Plugins"]

        # Test: Plugins → Browse → back → back (skips to repo when one repo)
        ctx, backend = create_context(temp_dir, ["plugins:browse", "_back", "_back"])
        plugin = PluginsPlugin()
        plugin.run(ctx)
        prompts = [c.prompt for c in backend.captures]
        assert prompts == ["Plugins", "Official", "Plugins"]


class TestNavigationPaths:
    """Test complete navigation paths through the menu system.

    Every selectable menu item should have at least one test path.

    Settings menu items:
    - _back: exits to main menu
    - settings:frequency: toggles frequency tracking, saves config
    - settings:backend: opens backend selection submenu
    - settings:rebuild: clears cache

    Settings > Select Backend items:
    - _back: returns to settings menu
    - settings:backend:auto: sets backend to auto-detect
    - settings:backend:rofi: sets backend to rofi
    - settings:backend:fuzzel: sets backend to fuzzel
    - settings:backend:dmenu: sets backend to dmenu
    - settings:backend:fzf: sets backend to fzf

    Plugins menu items:
    - _back: exits to main menu
    - plugins:installed: shows installed plugins submenu
    - plugins:browse: shows browse plugins submenu
    - plugins:updates: checks for updates (not yet implemented)

    Plugins > Installed items:
    - _back: returns to plugins menu
    - plugins:info:settings: shows settings plugin info
    - plugins:info:plugins: shows plugins plugin info

    Plugins > Browse items:
    - _back: returns to plugins menu
    - plugins:browse:info: info item (not selectable)
    - plugins:repo:*: repository items (not yet implemented)
    """

    @pytest.mark.parametrize(
        "path,expected_prompts",
        [
            # Back from settings
            (["_back"], ["Settings"]),
            # Toggle frequency (action)
            (
                ["settings:frequency", "_back"],
                ["Settings", "Settings"],
            ),
            # Backend submenu - back out
            (
                ["settings:backend", "_back", "_back"],
                ["Settings", "Select Backend", "Settings"],
            ),
            # Backend submenu - select option
            (
                ["settings:backend", "settings:backend:rofi", "_back"],
                ["Settings", "Select Backend", "Settings"],
            ),
            # Rebuild cache (action) - shows result menu
            (
                ["settings:rebuild", "_done", "_back"],
                ["Settings", "Rebuild Cache", "Settings"],
            ),
            # Multiple actions before exit
            (
                ["settings:frequency", "settings:rebuild", "_done", "_back"],
                ["Settings", "Settings", "Rebuild Cache", "Settings"],
            ),
        ],
    )
    def test_settings_paths(
        self, temp_dir: Path, path: list[str], expected_prompts: list[str]
    ) -> None:
        """Test various paths through settings menu."""
        ctx, backend = create_context(temp_dir, path)
        plugin = SettingsPlugin()

        plugin.run(ctx)

        prompts = [c.prompt for c in backend.captures]
        assert prompts == expected_prompts

    @pytest.mark.parametrize(
        "path,expected_prompts",
        [
            # Back from plugins main
            (["_back"], ["Plugins"]),
            # Check for updates action
            (
                ["plugins:updates", "_back"],
                ["Plugins", "Plugins"],
            ),
            # Navigate to Installed, then back
            (
                ["plugins:installed", "_back", "_back"],
                ["Plugins", "Installed Plugins", "Plugins"],
            ),
            # Navigate to Browse, then back (skips to repo with one repo)
            (
                ["plugins:browse", "_back", "_back"],
                ["Plugins", "Official", "Plugins"],
            ),
            # Select settings plugin in Installed, then back out
            (
                [
                    "plugins:installed",
                    "plugins:info:settings",
                    "_back",
                    "_back",
                    "_back",
                ],
                [
                    "Plugins",
                    "Installed Plugins",
                    "Settings",
                    "Installed Plugins",
                    "Plugins",
                ],
            ),
            # Select plugins plugin in Installed, then back out
            (
                [
                    "plugins:installed",
                    "plugins:info:plugins",
                    "_back",
                    "_back",
                    "_back",
                ],
                [
                    "Plugins",
                    "Installed Plugins",
                    "Plugins",
                    "Installed Plugins",
                    "Plugins",
                ],
            ),
            # Browse both installed plugins before backing out
            (
                [
                    "plugins:installed",
                    "plugins:info:settings",
                    "_back",
                    "plugins:info:plugins",
                    "_back",
                    "_back",
                    "_back",
                ],
                [
                    "Plugins",
                    "Installed Plugins",
                    "Settings",
                    "Installed Plugins",
                    "Plugins",
                    "Installed Plugins",
                    "Plugins",
                ],
            ),
            # Visit both submenus in one session (browse skips to repo with one repo)
            (
                [
                    "plugins:installed",
                    "_back",
                    "plugins:browse",
                    "_back",
                    "_back",
                ],
                [
                    "Plugins",
                    "Installed Plugins",
                    "Plugins",
                    "Official",  # Skips directly to repo plugins
                    "Plugins",
                ],
            ),
        ],
    )
    def test_plugins_paths(
        self, temp_dir: Path, path: list[str], expected_prompts: list[str]
    ) -> None:
        """Test various paths through plugins menu."""
        ctx, backend = create_context(temp_dir, path)
        plugin = PluginsPlugin()

        plugin.run(ctx)

        prompts = [c.prompt for c in backend.captures]
        assert prompts == expected_prompts

    def test_plugins_browse_repo_selection(self, temp_dir: Path) -> None:
        """Test browsing plugins with single repo skips to repo directly."""
        # Default config has one repository - should skip selection screen
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:browse",
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        plugin.run(ctx)

        prompts = [c.prompt for c in backend.captures]
        # With one repo, skips directly to repo plugins (Official)
        assert prompts == ["Plugins", "Official", "Plugins"]


class TestMenuItemBehavior:
    """Tests for what happens when each menu item is selected."""

    def test_settings_frequency_shows_notification(
        self,
        temp_dir: Path,
        capsys: pytest.CaptureFixture[str],
        disable_notify_send: None,
    ) -> None:
        """Selecting Frequency Tracking shows appropriate notification."""
        ctx, _ = create_context(temp_dir, ["settings:frequency", "_back"])
        plugin = SettingsPlugin()

        plugin.run(ctx)

        captured = capsys.readouterr()
        assert "frequency" in captured.out.lower()

    def test_settings_backend_selection_shows_notification(
        self,
        temp_dir: Path,
        capsys: pytest.CaptureFixture[str],
        disable_notify_send: None,
    ) -> None:
        """Selecting a backend option shows confirmation notification."""
        ctx, _ = create_context(temp_dir, ["settings:backend", "settings:backend:fzf", "_back"])
        plugin = SettingsPlugin()

        plugin.run(ctx)

        captured = capsys.readouterr()
        assert "backend" in captured.out.lower() or "fzf" in captured.out.lower()

    def test_settings_rebuild_shows_result(self, temp_dir: Path) -> None:
        """Selecting Rebuild Cache shows result screen."""
        # Need extra selection to dismiss the result menu
        ctx, backend = create_context(temp_dir, ["settings:rebuild", "_done", "_back"])
        plugin = SettingsPlugin()

        plugin.run(ctx)

        # Check that the result menu was shown
        result_menus = [c for c in backend.captures if c.prompt == "Rebuild Cache"]
        assert len(result_menus) == 1
        # Should show cache rebuilt message
        result_menu = result_menus[0]
        messages = [i.title.lower() for i in result_menu.items]
        assert any("cache" in m or "rebuilt" in m for m in messages)

    def test_plugins_updates_shows_notification(
        self,
        temp_dir: Path,
        capsys: pytest.CaptureFixture[str],
        disable_notify_send: None,
    ) -> None:
        """Selecting Check for Updates shows appropriate notification."""
        ctx, _ = create_context(temp_dir, ["plugins:updates", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        captured = capsys.readouterr()
        assert "update" in captured.out.lower()

    def test_plugins_installed_settings_toggle_shows_notification(
        self,
        temp_dir: Path,
        capsys: pytest.CaptureFixture[str],
        disable_notify_send: None,
    ) -> None:
        """Toggling display mode in plugin options shows notification."""
        ctx, _ = create_context(
            temp_dir,
            [
                "plugins:installed",
                "plugins:info:settings",
                "plugins:opt:settings:toggle",
                "_back",
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        plugin.run(ctx)

        captured = capsys.readouterr()
        assert "display mode" in captured.out.lower()

    def test_plugins_installed_plugins_toggle_shows_notification(
        self,
        temp_dir: Path,
        capsys: pytest.CaptureFixture[str],
        disable_notify_send: None,
    ) -> None:
        """Toggling display mode in plugin options shows notification."""
        ctx, _ = create_context(
            temp_dir,
            [
                "plugins:installed",
                "plugins:info:plugins",
                "plugins:opt:plugins:toggle",
                "_back",
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        plugin.run(ctx)

        captured = capsys.readouterr()
        assert "display mode" in captured.out.lower()

    def test_plugins_browse_repo_shows_plugins_or_error(
        self,
        temp_dir: Path,
        capsys: pytest.CaptureFixture[str],
        disable_notify_send: None,
    ) -> None:
        """Browsing shows plugins menu or error notification."""
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:browse",
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        plugin.run(ctx)

        captured = capsys.readouterr()
        prompts = [c.prompt for c in backend.captures]
        # With one repo, skips to repo plugins directly
        # Either shows error notification (no network) or shows repo menu (network ok)
        has_error = "failed" in captured.out.lower() or "fetch" in captured.out.lower()
        shows_repo_menu = "Official" in prompts
        assert has_error or shows_repo_menu

    def test_settings_frequency_badge_reflects_config(self, temp_dir: Path) -> None:
        """Frequency Tracking item shows current config state in badge."""
        # Default config has frequency_tracking=True
        ctx, backend = create_context(temp_dir, ["_back"])
        plugin = SettingsPlugin()

        plugin.run(ctx)

        menu = backend.captures[0]
        freq_item = next(i for i in menu.items if i.id == "settings:frequency")
        assert freq_item.badge == "On"

    def test_settings_backend_badge_shows_current(self, temp_dir: Path) -> None:
        """Menu Backend item shows current backend in badge."""
        ctx, backend = create_context(temp_dir, ["_back"])
        plugin = SettingsPlugin()

        plugin.run(ctx)

        menu = backend.captures[0]
        backend_item = next(i for i in menu.items if i.id == "settings:backend")
        # Default is empty string which displays as "auto"
        assert backend_item.badge == "auto"

    def test_plugins_installed_shows_version_badges(self, temp_dir: Path) -> None:
        """Installed plugins show version info in badges."""
        ctx, backend = create_context(temp_dir, ["plugins:installed", "_back", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        installed_menu = backend.captures[1]
        for item in installed_menu.items:
            if item.id.startswith("plugins:info:"):
                assert item.badge is not None
                assert "bundled" in item.badge or "0." in item.badge

    def test_plugins_main_shows_installed_count(self, temp_dir: Path) -> None:
        """Installed submenu shows count badge."""
        ctx, backend = create_context(temp_dir, ["_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        menu = backend.captures[0]
        installed_item = next(i for i in menu.items if i.id == "plugins:installed")
        assert installed_item.badge is not None
        # Should show a number (currently hardcoded to "2")
        assert installed_item.badge.isdigit() or installed_item.badge == "2"

    def test_plugins_browse_shows_official_not_path(self, temp_dir: Path) -> None:
        """Official repository shows as 'Official' not the repo path."""
        ctx, backend = create_context(temp_dir, ["plugins:browse", "_back", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        # With one repo, we skip directly to it - verify prompt is "Official"
        prompts = [c.prompt for c in backend.captures]
        assert "Official" in prompts
        # Should NOT show the full repo path as prompt
        assert "markhedleyjones" not in str(prompts)


class TestMenuItemConsistency:
    """Tests that menu items have consistent and valid properties."""

    def test_all_items_have_ids(self, temp_dir: Path) -> None:
        """All menu items must have non-empty IDs."""
        ctx, backend = create_context(
            temp_dir,
            ["plugins:installed", "_back", "plugins:browse", "_back", "_back"],
        )
        plugin = PluginsPlugin()
        plugin.run(ctx)

        for capture in backend.captures:
            for item in capture.items:
                assert item.id, f"Item '{item.title}' has empty ID"

    def test_all_items_have_titles(self, temp_dir: Path) -> None:
        """All menu items must have non-empty titles."""
        ctx, backend = create_context(
            temp_dir,
            ["plugins:installed", "_back", "plugins:browse", "_back", "_back"],
        )
        plugin = PluginsPlugin()
        plugin.run(ctx)

        for capture in backend.captures:
            for item in capture.items:
                assert item.title, f"Item '{item.id}' has empty title"

    def test_back_button_always_last(self, temp_dir: Path) -> None:
        """Back button should always be the last item when present."""
        ctx, backend = create_context(
            temp_dir,
            ["plugins:installed", "_back", "plugins:browse", "_back", "_back"],
        )
        plugin = PluginsPlugin()
        plugin.run(ctx)

        for capture in backend.captures:
            back_items = [i for i, item in enumerate(capture.items) if item.id == "_back"]
            if back_items:
                expected_pos = len(capture.items) - 1
                assert back_items[0] == expected_pos, f"Back button not last in '{capture.prompt}'"
