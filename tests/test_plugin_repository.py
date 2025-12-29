"""Tests for plugin repository browse/install/uninstall functionality.

These tests verify the complete plugin management flow:
1. Browse repositories
2. View available plugins
3. Install plugins
4. Verify installed plugins appear
5. Uninstall plugins
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from menu_kit.core.config import Config, get_data_dir
from menu_kit.core.database import Database, ItemType, MenuItem
from menu_kit.menu.base import MenuBackend, MenuResult
from menu_kit.plugins.base import Plugin, PluginContext
from menu_kit.plugins.builtin.plugins import PluginsPlugin
from menu_kit.plugins.builtin.settings import SettingsPlugin

if TYPE_CHECKING:
    pass


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

        # Find the item by ID
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


# Mock index data for offline tests
MOCK_INDEX = {
    "version": 1,
    "plugins": {
        "test-plugin": {
            "version": "1.0.0",
            "description": "A test plugin for testing",
            "api_version": "1",
            "download": "plugins/test-plugin",
        },
        "another-plugin": {
            "version": "2.0.0",
            "description": "Another plugin for testing",
            "api_version": "1",
            "download": "plugins/another-plugin",
        },
    },
}


class TestBrowseMenuStructure:
    """Tests for the Browse Plugins menu structure."""

    def test_browse_menu_shows_info_and_repositories(self, temp_dir: Path) -> None:
        """Browse menu shows info item and repository list."""
        ctx, backend = create_context(temp_dir, ["plugins:browse", "_back", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        # Find the Browse menu capture
        browse_menu = backend.captures[1]
        assert browse_menu.prompt == "Browse Plugins"

        # Should have info item
        info_items = [i for i in browse_menu.items if i.id == "plugins:browse:info"]
        assert len(info_items) == 1
        assert (
            "repository" in info_items[0].title.lower()
            or "connect" in info_items[0].title.lower()
        )

        # Should have at least one repository
        repo_items = [i for i in browse_menu.items if i.id.startswith("plugins:repo:")]
        assert len(repo_items) >= 1

    def test_browse_menu_shows_official_repo_with_friendly_name(
        self, temp_dir: Path
    ) -> None:
        """Official repository shows as 'Official' not the repo path."""
        ctx, backend = create_context(temp_dir, ["plugins:browse", "_back", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        browse_menu = backend.captures[1]
        repo_items = [i for i in browse_menu.items if i.id.startswith("plugins:repo:")]

        # Find the official repo
        official_items = [
            i for i in repo_items if "markhedleyjones/menu-kit-plugins" in i.id
        ]
        assert len(official_items) == 1
        assert official_items[0].title == "Official"


class TestRepositoryPluginsList:
    """Tests for the repository plugins list (requires network or mock)."""

    def test_repo_shows_available_plugins_with_mock(self, temp_dir: Path) -> None:
        """Repository menu shows available plugins (mocked)."""
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:browse",
                "plugins:repo:markhedleyjones/menu-kit-plugins",
                "_back",
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        # Mock the fetch to return our test data
        with patch.object(plugin, "_fetch_repo_index", return_value=MOCK_INDEX):
            plugin.run(ctx)

        # Find the repo plugins menu (prompt should be "Official")
        repo_menus = [c for c in backend.captures if c.prompt == "Official"]
        assert len(repo_menus) == 1

        repo_menu = repo_menus[0]
        plugin_items = [
            i for i in repo_menu.items if i.id.startswith("plugins:available:")
        ]

        # Should show both test plugins
        assert len(plugin_items) == 2
        plugin_names = {i.title for i in plugin_items}
        assert "test-plugin" in plugin_names
        assert "another-plugin" in plugin_names

    def test_repo_plugins_show_version_badges(self, temp_dir: Path) -> None:
        """Available plugins show version in badge."""
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:browse",
                "plugins:repo:markhedleyjones/menu-kit-plugins",
                "_back",
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        with patch.object(plugin, "_fetch_repo_index", return_value=MOCK_INDEX):
            plugin.run(ctx)

        repo_menu = next(c for c in backend.captures if c.prompt == "Official")
        plugin_items = [
            i for i in repo_menu.items if i.id.startswith("plugins:available:")
        ]

        for item in plugin_items:
            assert item.badge is not None
            assert "v" in item.badge or "." in item.badge  # Version format


class TestPluginInstallScreen:
    """Tests for the plugin install/details screen."""

    def test_plugin_details_shows_description(self, temp_dir: Path) -> None:
        """Plugin details screen shows description."""
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:browse",
                "plugins:repo:markhedleyjones/menu-kit-plugins",
                "plugins:available:markhedleyjones/menu-kit-plugins:test-plugin",
                "_back",
                "_back",
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        with patch.object(plugin, "_fetch_repo_index", return_value=MOCK_INDEX):
            plugin.run(ctx)

        # Find the plugin details menu (prompt should be plugin name title-cased)
        detail_menus = [c for c in backend.captures if c.prompt == "Test-Plugin"]
        assert len(detail_menus) == 1

        detail_menu = detail_menus[0]

        # Should have description as info item
        desc_items = [i for i in detail_menu.items if i.item_type == ItemType.INFO]
        assert len(desc_items) >= 1
        descriptions = [i.title for i in desc_items]
        assert any("test" in d.lower() for d in descriptions)

    def test_plugin_details_shows_install_option(self, temp_dir: Path) -> None:
        """Plugin details screen shows Install option for uninstalled plugin."""
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:browse",
                "plugins:repo:markhedleyjones/menu-kit-plugins",
                "plugins:available:markhedleyjones/menu-kit-plugins:test-plugin",
                "_back",
                "_back",
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        with patch.object(plugin, "_fetch_repo_index", return_value=MOCK_INDEX):
            plugin.run(ctx)

        detail_menu = next(c for c in backend.captures if c.prompt == "Test-Plugin")

        # Should have Install action
        install_items = [i for i in detail_menu.items if "install" in i.id.lower()]
        assert len(install_items) == 1
        assert install_items[0].item_type == ItemType.ACTION


class TestPluginInstallFlow:
    """Tests for actually installing plugins."""

    def test_install_plugin_creates_directory(self, temp_dir: Path) -> None:
        """Installing a plugin creates the plugin directory."""
        from unittest.mock import MagicMock

        plugin = PluginsPlugin()

        # Create a mock context
        class MockCtx:
            config = Config.load(temp_dir / "config.toml")
            database = Database(temp_dir / "test.db")

        # Mock the download to avoid network
        mock_content = b'"""Test plugin."""\n\ndef create_plugin(): pass\n'

        with patch(
            "menu_kit.plugins.builtin.plugins.urllib.request.urlopen"
        ) as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = mock_content
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            result = plugin._install_plugin(
                MockCtx(),
                "test/repo",
                "my-plugin",
                {"download": "plugins/my-plugin"},
            )

        assert result is True
        plugin_dir = get_data_dir() / "plugins" / "my-plugin"
        assert plugin_dir.exists()
        assert (plugin_dir / "__init__.py").exists()

        # Cleanup
        shutil.rmtree(plugin_dir)

    def test_install_shows_success_notification(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Installing a plugin shows success notification."""
        from unittest.mock import MagicMock

        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:browse",
                "plugins:repo:markhedleyjones/menu-kit-plugins",
                "plugins:available:markhedleyjones/menu-kit-plugins:test-plugin",
                "plugins:detail:test-plugin:install",
                "_back",
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        mock_content = b'"""Test plugin."""\n\ndef create_plugin(): pass\n'

        with (
            patch.object(plugin, "_fetch_repo_index", return_value=MOCK_INDEX),
            patch(
                "menu_kit.plugins.builtin.plugins.urllib.request.urlopen"
            ) as mock_urlopen,
        ):
            mock_response = MagicMock()
            mock_response.read.return_value = mock_content
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            plugin.run(ctx)

        captured = capsys.readouterr()
        assert "installed" in captured.out.lower()

        # Cleanup
        plugin_dir = get_data_dir() / "plugins" / "test-plugin"
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)


class TestInstalledPluginsScreen:
    """Tests for the Installed Plugins screen."""

    def test_installed_shows_bundled_plugins(self, temp_dir: Path) -> None:
        """Installed plugins screen shows bundled plugins."""
        ctx, backend = create_context(temp_dir, ["plugins:installed", "_back", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        installed_menu = backend.captures[1]
        assert installed_menu.prompt == "Installed Plugins"

        plugin_items = [
            i for i in installed_menu.items if i.id.startswith("plugins:info:")
        ]

        # Should show settings and plugins (bundled)
        plugin_ids = [i.id for i in plugin_items]
        assert "plugins:info:settings" in plugin_ids
        assert "plugins:info:plugins" in plugin_ids

    def test_installed_shows_version_and_source(self, temp_dir: Path) -> None:
        """Installed plugins show version and source (bundled/installed) in badge."""
        ctx, backend = create_context(temp_dir, ["plugins:installed", "_back", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        installed_menu = backend.captures[1]
        plugin_items = [
            i for i in installed_menu.items if i.id.startswith("plugins:info:")
        ]

        for item in plugin_items:
            assert item.badge is not None
            # Should contain version and source
            assert "." in item.badge  # Version
            assert "bundled" in item.badge or "installed" in item.badge


class TestPluginOptionsScreen:
    """Tests for the plugin options screen."""

    def test_plugin_options_shows_info_and_toggle(self, temp_dir: Path) -> None:
        """Plugin options screen shows info and display mode toggle."""
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:installed",
                "plugins:info:settings",
                "_back",
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        plugin.run(ctx)

        # Find the options menu (prompt is plugin name title-cased)
        options_menu = next(c for c in backend.captures if c.prompt == "Settings")

        # Should have info item with version
        info_items = [i for i in options_menu.items if ":info" in i.id]
        assert len(info_items) >= 1

        # Should have toggle option
        toggle_items = [i for i in options_menu.items if ":toggle" in i.id]
        assert len(toggle_items) == 1
        # Toggle should show current mode
        assert toggle_items[0].badge is not None
        assert "inline" in toggle_items[0].badge or "submenu" in toggle_items[0].badge

    def test_bundled_plugins_no_uninstall_option(self, temp_dir: Path) -> None:
        """Bundled plugins (settings, plugins) don't show uninstall option."""
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:installed",
                "plugins:info:settings",
                "_back",
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        plugin.run(ctx)

        options_menu = next(c for c in backend.captures if c.prompt == "Settings")

        # Should NOT have uninstall option for bundled plugin
        uninstall_items = [i for i in options_menu.items if ":uninstall" in i.id]
        assert len(uninstall_items) == 0


class TestPluginUninstallFlow:
    """Tests for uninstalling plugins."""

    def test_uninstall_removes_plugin_directory(self, temp_dir: Path) -> None:
        """Uninstalling a plugin removes its directory."""
        plugin = PluginsPlugin()

        # Create a fake installed plugin
        plugins_dir = get_data_dir() / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        test_plugin_dir = plugins_dir / "uninstall-test"
        test_plugin_dir.mkdir(exist_ok=True)
        (test_plugin_dir / "__init__.py").write_text('"""Test."""\n')

        assert test_plugin_dir.exists()

        class MockCtx:
            database = Database(temp_dir / "test.db")

        result = plugin._uninstall_plugin(MockCtx(), "uninstall-test")

        assert result is True
        assert not test_plugin_dir.exists()

    def test_uninstall_removes_symlinked_plugin(self, temp_dir: Path) -> None:
        """Uninstalling a symlinked plugin removes the symlink."""
        plugin = PluginsPlugin()

        # Create a source directory and symlink
        source_dir = temp_dir / "source-plugin"
        source_dir.mkdir(exist_ok=True)
        (source_dir / "__init__.py").write_text('"""Test."""\n')

        plugins_dir = get_data_dir() / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        symlink = plugins_dir / "symlink-test"
        symlink.symlink_to(source_dir)

        assert symlink.is_symlink()

        class MockCtx:
            database = Database(temp_dir / "test.db")

        result = plugin._uninstall_plugin(MockCtx(), "symlink-test")

        assert result is True
        assert not symlink.exists()
        # Source should still exist
        assert source_dir.exists()


class TestRealNetworkIntegration:
    """Integration tests that use real network (marked for optional skip)."""

    @pytest.mark.network
    def test_fetch_real_index_from_github(self) -> None:
        """Can fetch real index.json from GitHub."""
        plugin = PluginsPlugin()
        index = plugin._fetch_repo_index("markhedleyjones/menu-kit-plugins")

        assert index is not None
        assert "version" in index
        assert "plugins" in index
        assert isinstance(index["plugins"], dict)

    @pytest.mark.network
    def test_real_index_has_expected_structure(self) -> None:
        """Real index.json has expected plugin structure."""
        plugin = PluginsPlugin()
        index = plugin._fetch_repo_index("markhedleyjones/menu-kit-plugins")

        assert index is not None

        for _name, info in index["plugins"].items():
            assert "version" in info
            assert "description" in info
            assert "download" in info

    @pytest.mark.network
    def test_can_install_real_plugin(self, temp_dir: Path) -> None:
        """Can install a real plugin from GitHub."""
        plugin = PluginsPlugin()
        index = plugin._fetch_repo_index("markhedleyjones/menu-kit-plugins")

        assert index is not None
        assert len(index["plugins"]) > 0

        # Pick the first available plugin
        plugin_name = next(iter(index["plugins"].keys()))
        plugin_info = index["plugins"][plugin_name]

        class MockCtx:
            pass

        # Remove if already exists
        plugin_dir = get_data_dir() / "plugins" / plugin_name
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)

        result = plugin._install_plugin(
            MockCtx(), "markhedleyjones/menu-kit-plugins", plugin_name, plugin_info
        )

        assert result is True
        assert plugin_dir.exists()
        assert (plugin_dir / "__init__.py").exists()

        # Verify the file has content
        content = (plugin_dir / "__init__.py").read_text()
        assert len(content) > 0
        assert "def" in content or "class" in content

        # Cleanup
        shutil.rmtree(plugin_dir)
