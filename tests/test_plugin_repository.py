"""Tests for plugin repository browse/install/uninstall functionality.

These tests verify the complete plugin management flow:
1. Browse repositories
2. View available plugins
3. Install plugins
4. Verify installed plugins appear
5. Uninstall plugins
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from menu_kit.core.config import Config
from menu_kit.core.database import Database, ItemType, MenuItem
from menu_kit.menu.base import MenuBackend, MenuResult
from menu_kit.plugins.base import MenuCancelled, Plugin, PluginContext
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

    def test_browse_menu_skips_to_repo_with_single_repo(self, temp_dir: Path) -> None:
        """With one repo configured, browse skips directly to that repo."""
        ctx, backend = create_context(temp_dir, ["plugins:browse", "_back", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        # With one repo, should skip directly to "Official" (repo plugins menu)
        prompts = [c.prompt for c in backend.captures]
        assert prompts == ["Plugins", "Official", "Plugins"]

    def test_browse_menu_shows_official_as_prompt(self, temp_dir: Path) -> None:
        """Official repository shows as 'Official' not the repo path."""
        ctx, backend = create_context(temp_dir, ["plugins:browse", "_back", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        # With one repo, prompt should be "Official"
        prompts = [c.prompt for c in backend.captures]
        assert "Official" in prompts
        # Should NOT show the full repo path
        assert "markhedleyjones" not in str(prompts)


class TestRepositoryPluginsList:
    """Tests for the repository plugins list (requires network or mock)."""

    def test_repo_shows_available_plugins_with_mock(self, temp_dir: Path) -> None:
        """Repository menu shows available plugins (mocked)."""
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:browse",
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
        plugin_items = [i for i in repo_menu.items if i.id.startswith("plugins:available:")]

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
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        with patch.object(plugin, "_fetch_repo_index", return_value=MOCK_INDEX):
            plugin.run(ctx)

        repo_menu = next(c for c in backend.captures if c.prompt == "Official")
        plugin_items = [i for i in repo_menu.items if i.id.startswith("plugins:available:")]

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
                "plugins:available:markhedleyjones/menu-kit-plugins:test-plugin",
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
                "plugins:available:markhedleyjones/menu-kit-plugins:test-plugin",
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

    def test_install_plugin_creates_directory(
        self, temp_dir: Path, sandbox_environment: Path
    ) -> None:
        """Installing a plugin creates the plugin directory."""
        from unittest.mock import MagicMock

        plugin = PluginsPlugin()

        # Create a mock context
        class MockCtx:
            config = Config.load(temp_dir / "config.toml")
            database = Database(temp_dir / "test.db")

        # Mock the download to avoid network
        mock_content = b'"""Test plugin."""\n\ndef create_plugin(): pass\n'

        with patch("menu_kit.plugins.builtin.plugins.urllib.request.urlopen") as mock_urlopen:
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
        # Use sandboxed data directory
        data_dir = sandbox_environment / "data"
        plugin_dir = data_dir / "plugins" / "my-plugin"
        assert plugin_dir.exists()
        assert (plugin_dir / "__init__.py").exists()

    def test_install_shows_result_screen(self, temp_dir: Path, sandbox_environment: Path) -> None:
        """Installing a plugin shows result screen."""
        from unittest.mock import MagicMock

        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:browse",
                "plugins:available:markhedleyjones/menu-kit-plugins:test-plugin",
                "plugins:detail:test-plugin:install",
                "_done",  # Dismiss result screen
                "_back",
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        mock_content = b'"""Test plugin."""\n\ndef create_plugin(): pass\n'

        with (
            patch.object(plugin, "_fetch_repo_index", return_value=MOCK_INDEX),
            patch("menu_kit.plugins.builtin.plugins.urllib.request.urlopen") as mock_urlopen,
        ):
            mock_response = MagicMock()
            mock_response.read.return_value = mock_content
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with contextlib.suppress(MenuCancelled):
                plugin.run(ctx)

        # Check result screen was shown
        result_menus = [c for c in backend.captures if c.prompt == "Install Plugin"]
        assert len(result_menus) == 1
        # Should show installed message
        messages = [i.title.lower() for i in result_menus[0].items]
        assert any("installed" in m for m in messages)


class TestInstalledPluginsScreen:
    """Tests for the Installed Plugins screen."""

    def test_installed_shows_bundled_plugins(self, temp_dir: Path) -> None:
        """Installed plugins screen shows bundled plugins."""
        ctx, backend = create_context(temp_dir, ["plugins:installed", "_back", "_back"])
        plugin = PluginsPlugin()

        plugin.run(ctx)

        installed_menu = backend.captures[1]
        assert installed_menu.prompt == "Installed Plugins"

        plugin_items = [i for i in installed_menu.items if i.id.startswith("plugins:info:")]

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
        plugin_items = [i for i in installed_menu.items if i.id.startswith("plugins:info:")]

        for item in plugin_items:
            assert item.badge is not None
            # Should contain version and source
            assert "." in item.badge  # Version
            assert "bundled" in item.badge or "installed" in item.badge


class TestPluginOptionsScreen:
    """Tests for the plugin options screen."""

    def test_plugin_options_shows_info(self, temp_dir: Path) -> None:
        """Plugin options screen shows info."""
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

        # Settings/Plugins should NOT have toggle (submenu-only plugins)
        toggle_items = [i for i in options_menu.items if ":toggle" in i.id]
        assert len(toggle_items) == 0

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

    def test_uninstall_removes_plugin_directory(
        self, temp_dir: Path, sandbox_environment: Path
    ) -> None:
        """Uninstalling a plugin removes its directory."""
        plugin = PluginsPlugin()

        # Create a fake installed plugin in sandboxed data dir
        data_dir = sandbox_environment / "data"
        plugins_dir = data_dir / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        test_plugin_dir = plugins_dir / "uninstall-test"
        test_plugin_dir.mkdir(exist_ok=True)
        (test_plugin_dir / "__init__.py").write_text('"""Test."""\n')

        assert test_plugin_dir.exists()

        class MockCtx:
            database = Database(temp_dir / "test.db")

            def unregister_plugin(self, name: str) -> bool:
                return True

        result = plugin._uninstall_plugin(MockCtx(), "uninstall-test")

        assert result is True
        assert not test_plugin_dir.exists()

    def test_uninstall_removes_symlinked_plugin(
        self, temp_dir: Path, sandbox_environment: Path
    ) -> None:
        """Uninstalling a symlinked plugin removes the symlink."""
        plugin = PluginsPlugin()

        # Create a source directory and symlink
        source_dir = temp_dir / "source-plugin"
        source_dir.mkdir(exist_ok=True)
        (source_dir / "__init__.py").write_text('"""Test."""\n')

        data_dir = sandbox_environment / "data"
        plugins_dir = data_dir / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        symlink = plugins_dir / "symlink-test"
        symlink.symlink_to(source_dir)

        assert symlink.is_symlink()

        class MockCtx:
            database = Database(temp_dir / "test.db")

            def unregister_plugin(self, name: str) -> bool:
                return True

        result = plugin._uninstall_plugin(MockCtx(), "symlink-test")

        assert result is True
        assert not symlink.exists()
        # Source should still exist
        assert source_dir.exists()


class TestUninstallViaMenu:
    """Tests for uninstalling plugins through the menu interface."""

    def test_uninstall_removes_plugin_from_installed_list(
        self, temp_dir: Path, sandbox_environment: Path
    ) -> None:
        """After uninstalling, plugin no longer appears in installed list."""
        from menu_kit.plugins.base import PluginInfo

        # Create a fake plugin that can be uninstalled in sandboxed dir
        data_dir = sandbox_environment / "data"
        plugins_dir = data_dir / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        test_plugin_dir = plugins_dir / "test-uninstall"
        test_plugin_dir.mkdir(exist_ok=True)
        (test_plugin_dir / "__init__.py").write_text('"""Test."""\n')

        # Create a mock loader that tracks registrations
        class TrackingLoader:
            def __init__(self) -> None:
                self._plugins: dict[str, Plugin] = {}

            def get_all_plugins(self) -> dict[str, Plugin]:
                return self._plugins

            def register(self, plugin: Plugin) -> None:
                self._plugins[plugin.info.name] = plugin

            def unregister_plugin(self, name: str) -> bool:
                if name in self._plugins:
                    del self._plugins[name]
                    return True
                return False

            def index_all(self) -> None:
                """Mock index_all."""

        # Create a fake plugin object for test-uninstall
        class FakePlugin:
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name="test-uninstall", version="1.0.0")

        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:installed",
                "plugins:info:test-uninstall",
                "plugins:opt:test-uninstall:uninstall",
                "_done",  # Dismiss result screen
                "_back",  # Back to installed (should not show test-uninstall)
                "_back",  # Back to plugins menu
            ],
        )

        # Replace loader with tracking version
        loader = TrackingLoader()
        loader.register(SettingsPlugin())
        loader.register(PluginsPlugin())
        loader.register(FakePlugin())  # type: ignore[arg-type]
        ctx._loader = loader  # type: ignore[attr-defined]

        plugin = PluginsPlugin()
        plugin.run(ctx)

        # Verify result screen was shown
        result_menus = [c for c in backend.captures if c.prompt == "Uninstall Plugin"]
        assert len(result_menus) == 1
        messages = [i.title.lower() for i in result_menus[0].items]
        assert any("uninstalled" in m for m in messages)

        # Verify plugin is no longer in loader
        assert "test-uninstall" not in loader.get_all_plugins()

        # Verify the installed list was shown again and doesn't contain test-uninstall
        installed_menus = [c for c in backend.captures if c.prompt == "Installed Plugins"]
        assert len(installed_menus) >= 2  # Before and after uninstall

        # The last installed menu should not have test-uninstall
        last_installed = installed_menus[-1]
        plugin_ids = [i.id for i in last_installed.items]
        assert "plugins:info:test-uninstall" not in plugin_ids

    def test_uninstall_option_shown_for_installed_plugins(
        self, temp_dir: Path, sandbox_environment: Path
    ) -> None:
        """Installed (non-bundled) plugins show uninstall option."""
        from menu_kit.plugins.base import PluginInfo

        # Create a fake plugin in sandboxed dir
        data_dir = sandbox_environment / "data"
        plugins_dir = data_dir / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        test_plugin_dir = plugins_dir / "my-plugin"
        test_plugin_dir.mkdir(exist_ok=True)
        (test_plugin_dir / "__init__.py").write_text('"""Test."""\n')

        class FakePlugin:
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name="my-plugin", version="1.0.0")

        class TrackingLoader:
            def __init__(self) -> None:
                self._plugins: dict[str, Plugin] = {}

            def get_all_plugins(self) -> dict[str, Plugin]:
                return self._plugins

            def register(self, plugin: Plugin) -> None:
                self._plugins[plugin.info.name] = plugin

            def unregister_plugin(self, name: str) -> bool:
                if name in self._plugins:
                    del self._plugins[name]
                    return True
                return False

            def index_all(self) -> None:
                """Mock index_all."""

        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:installed",
                "plugins:info:my-plugin",
                "_back",
                "_back",
                "_back",
            ],
        )

        loader = TrackingLoader()
        loader.register(SettingsPlugin())
        loader.register(PluginsPlugin())
        loader.register(FakePlugin())  # type: ignore[arg-type]
        ctx._loader = loader  # type: ignore[attr-defined]

        plugin = PluginsPlugin()
        plugin.run(ctx)

        # Find the plugin options menu
        options_menus = [c for c in backend.captures if c.prompt == "My-Plugin"]
        assert len(options_menus) == 1

        options_menu = options_menus[0]
        uninstall_items = [i for i in options_menu.items if ":uninstall" in i.id]
        assert len(uninstall_items) == 1


class TestFullMenuFlowInstall:
    """Integration test for installing a plugin through the full menu flow."""

    def test_install_plugin_through_menu_flow(
        self, temp_dir: Path, sandbox_environment: Path
    ) -> None:
        """Install a plugin by navigating through all menus."""
        from unittest.mock import MagicMock

        # Verify we're using the sandboxed data dir
        data_dir = sandbox_environment / "data"
        plugins_dir = data_dir / "plugins"

        # Build selections for full flow:
        # 1. Plugins main menu
        # 2. Install New Plugins (browse)
        # 3. Select test-plugin from list
        # 4. Click install
        # 5. Dismiss result screen
        # 6. Back out
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:browse",  # Install New Plugins
                "plugins:available:markhedleyjones/menu-kit-plugins:test-plugin",
                "plugins:detail:test-plugin:install",
                "_done",  # Dismiss result screen
                "_back",  # Back to repo plugins
                "_back",  # Back to plugins main menu (exits since single repo)
            ],
        )

        plugin = PluginsPlugin()

        mock_content = b'"""Test plugin."""\n\ndef create_plugin(): pass\n'

        with (
            patch.object(plugin, "_fetch_repo_index", return_value=MOCK_INDEX),
            patch("menu_kit.plugins.builtin.plugins.urllib.request.urlopen") as mock_urlopen,
        ):
            mock_response = MagicMock()
            mock_response.read.return_value = mock_content
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with contextlib.suppress(MenuCancelled):
                plugin.run(ctx)

        # Verify the plugin was installed in the sandboxed directory
        installed_plugin_dir = plugins_dir / "test-plugin"
        assert installed_plugin_dir.exists(), f"Plugin not found at {installed_plugin_dir}"
        assert (installed_plugin_dir / "__init__.py").exists()

        # Verify content
        content = (installed_plugin_dir / "__init__.py").read_text()
        assert "Test plugin" in content

        # Verify result screen was shown
        result_menus = [c for c in backend.captures if c.prompt == "Install Plugin"]
        assert len(result_menus) == 1
        messages = [i.title.lower() for i in result_menus[0].items]
        assert any("installed" in m for m in messages)

    def test_install_then_view_in_installed_list(
        self, temp_dir: Path, sandbox_environment: Path
    ) -> None:
        """After installing a plugin, it appears in the installed list."""
        from unittest.mock import MagicMock

        from menu_kit.plugins.base import PluginInfo

        # Create a fake plugin that simulates being installed
        class FakeInstalledPlugin:
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name="test-plugin", version="1.0.0", description="Test")

        # Build selections: install, then view installed
        # With single repo, browse goes directly to repo plugins, so only one _back
        # is needed after install to return to main menu
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:browse",  # Install New Plugins (main menu)
                "plugins:available:markhedleyjones/menu-kit-plugins:test-plugin",  # repo
                "plugins:detail:test-plugin:install",  # plugin details
                "_done",  # Dismiss result screen
                "_back",  # Exit repo list (returns to main menu with single repo)
                "plugins:installed",  # View installed (main menu)
                "_back",  # Exit installed list
                "_back",  # Exit main menu
            ],
        )

        # Register the fake plugin so it shows in installed list after install
        class TrackingLoader:
            def __init__(self) -> None:
                self._plugins: dict[str, Plugin] = {}

            def get_all_plugins(self) -> dict[str, Plugin]:
                return self._plugins

            def register(self, plugin: Plugin) -> None:
                self._plugins[plugin.info.name] = plugin

            def unregister_plugin(self, name: str) -> bool:
                if name in self._plugins:
                    del self._plugins[name]
                    return True
                return False

            def index_all(self) -> None:
                pass

        loader = TrackingLoader()
        loader.register(SettingsPlugin())
        loader.register(PluginsPlugin())
        ctx._loader = loader  # type: ignore[attr-defined]

        plugin = PluginsPlugin()

        mock_content = b'"""Test plugin."""\n\ndef create_plugin(): pass\n'

        def simulate_install(*args, **kwargs):
            # Simulate the plugin being installed by registering it
            loader.register(FakeInstalledPlugin())  # type: ignore[arg-type]
            mock_response = MagicMock()
            mock_response.read.return_value = mock_content
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with (
            patch.object(plugin, "_fetch_repo_index", return_value=MOCK_INDEX),
            patch(
                "menu_kit.plugins.builtin.plugins.urllib.request.urlopen",
                side_effect=simulate_install,
            ),
            contextlib.suppress(MenuCancelled),
        ):
            plugin.run(ctx)

        # Find the installed plugins menu shown AFTER the install
        installed_menus = [c for c in backend.captures if c.prompt == "Installed Plugins"]
        assert len(installed_menus) >= 1

        # The installed menu should show test-plugin
        last_installed = installed_menus[-1]
        plugin_ids = [i.id for i in last_installed.items]
        assert "plugins:info:test-plugin" in plugin_ids


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
    def test_can_install_real_plugin(self, sandbox_environment: Path) -> None:
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

        result = plugin._install_plugin(
            MockCtx(), "markhedleyjones/menu-kit-plugins", plugin_name, plugin_info
        )

        assert result is True
        # Use sandboxed data dir
        data_dir = sandbox_environment / "data"
        plugin_dir = data_dir / "plugins" / plugin_name
        assert plugin_dir.exists()
        assert (plugin_dir / "__init__.py").exists()

        # Verify the file has content
        content = (plugin_dir / "__init__.py").read_text()
        assert len(content) > 0
        assert "def" in content or "class" in content


class TestVersionComparison:
    """Tests for version comparison logic."""

    def test_newer_major_version(self) -> None:
        """Major version bump is detected as newer."""
        plugin = PluginsPlugin()
        assert plugin._version_is_newer("2.0.0", "1.0.0") is True

    def test_newer_minor_version(self) -> None:
        """Minor version bump is detected as newer."""
        plugin = PluginsPlugin()
        assert plugin._version_is_newer("1.1.0", "1.0.0") is True

    def test_newer_patch_version(self) -> None:
        """Patch version bump is detected as newer."""
        plugin = PluginsPlugin()
        assert plugin._version_is_newer("1.0.1", "1.0.0") is True

    def test_same_version_not_newer(self) -> None:
        """Same version is not newer."""
        plugin = PluginsPlugin()
        assert plugin._version_is_newer("1.0.0", "1.0.0") is False

    def test_older_version_not_newer(self) -> None:
        """Older version is not newer."""
        plugin = PluginsPlugin()
        assert plugin._version_is_newer("1.0.0", "2.0.0") is False

    def test_different_length_versions(self) -> None:
        """Handles versions with different numbers of parts."""
        plugin = PluginsPlugin()
        assert plugin._version_is_newer("1.0.0.1", "1.0.0") is True
        assert plugin._version_is_newer("1.0", "1.0.0") is False


class TestUpdateCheckNoPlugins:
    """Tests for update check when no plugins are installed."""

    def test_no_plugins_shows_message(self, temp_dir: Path) -> None:
        """When no non-bundled plugins installed, shows appropriate message."""
        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:updates",
                "_done",  # Dismiss result screen
                "_back",
            ],
        )
        plugin = PluginsPlugin()

        plugin.run(ctx)

        # Should show result screen with "no installed plugins" message
        result_menus = [c for c in backend.captures if c.prompt == "Update Plugins"]
        assert len(result_menus) == 1
        messages = [i.title.lower() for i in result_menus[0].items]
        assert any("no installed" in m for m in messages)


class TestUpdateCheckAllUpToDate:
    """Tests for update check when all plugins are up to date."""

    def test_all_up_to_date_shows_message(
        self, temp_dir: Path, sandbox_environment: Path
    ) -> None:
        """When all plugins are current, shows 'all up to date' message."""
        from menu_kit.plugins.base import PluginInfo

        # Create a fake installed plugin with same version as in repo
        class FakePlugin:
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name="test-plugin", version="1.0.0")

        # Mock index returns same version as installed
        mock_index = {
            "version": 1,
            "plugins": {
                "test-plugin": {
                    "version": "1.0.0",
                    "description": "Test plugin",
                    "download": "plugins/test-plugin",
                },
            },
        }

        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:updates",
                "_done",  # Dismiss result screen
                "_back",
            ],
        )

        # Set up loader with fake plugin
        class TrackingLoader:
            def __init__(self) -> None:
                self._plugins: dict[str, Plugin] = {}

            def get_all_plugins(self) -> dict[str, Plugin]:
                return self._plugins

            def register(self, plugin: Plugin) -> None:
                self._plugins[plugin.info.name] = plugin

        loader = TrackingLoader()
        loader.register(SettingsPlugin())
        loader.register(PluginsPlugin())
        loader.register(FakePlugin())  # type: ignore[arg-type]
        ctx._loader = loader  # type: ignore[attr-defined]

        plugin = PluginsPlugin()

        with patch.object(plugin, "_fetch_repo_index", return_value=mock_index):
            plugin.run(ctx)

        # Should show "all up to date" message
        result_menus = [c for c in backend.captures if c.prompt == "Update Plugins"]
        assert len(result_menus) == 1
        messages = [i.title.lower() for i in result_menus[0].items]
        assert any("up to date" in m for m in messages)


class TestUpdateAvailableMenu:
    """Tests for the updates available menu."""

    def test_shows_update_available(
        self, temp_dir: Path, sandbox_environment: Path
    ) -> None:
        """Shows plugin with available update in menu."""
        from menu_kit.plugins.base import PluginInfo

        # Installed version 1.0.0, repo has 2.0.0
        class FakePlugin:
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name="test-plugin", version="1.0.0")

        mock_index = {
            "version": 1,
            "plugins": {
                "test-plugin": {
                    "version": "2.0.0",
                    "description": "Test plugin",
                    "download": "plugins/test-plugin",
                },
            },
        }

        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:updates",
                "_back",  # Back from updates menu
                "_back",
            ],
        )

        class TrackingLoader:
            def __init__(self) -> None:
                self._plugins: dict[str, Plugin] = {}

            def get_all_plugins(self) -> dict[str, Plugin]:
                return self._plugins

            def register(self, plugin: Plugin) -> None:
                self._plugins[plugin.info.name] = plugin

        loader = TrackingLoader()
        loader.register(SettingsPlugin())
        loader.register(PluginsPlugin())
        loader.register(FakePlugin())  # type: ignore[arg-type]
        ctx._loader = loader  # type: ignore[attr-defined]

        plugin = PluginsPlugin()

        with patch.object(plugin, "_fetch_repo_index", return_value=mock_index):
            plugin.run(ctx)

        # Should show updates available menu
        update_menus = [c for c in backend.captures if c.prompt == "Updates Available"]
        assert len(update_menus) == 1

        # Should list the plugin with version badge
        update_menu = update_menus[0]
        plugin_items = [i for i in update_menu.items if i.id == "plugins:update:test-plugin"]
        assert len(plugin_items) == 1
        assert "1.0.0" in plugin_items[0].badge
        assert "2.0.0" in plugin_items[0].badge

    def test_shows_update_all_with_multiple_updates(
        self, temp_dir: Path, sandbox_environment: Path
    ) -> None:
        """Shows 'Update All' option when multiple updates available."""
        from menu_kit.plugins.base import PluginInfo

        class FakePlugin1:
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name="plugin-one", version="1.0.0")

        class FakePlugin2:
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name="plugin-two", version="1.0.0")

        mock_index = {
            "version": 1,
            "plugins": {
                "plugin-one": {"version": "2.0.0", "description": "One", "download": "plugins/plugin-one"},
                "plugin-two": {"version": "2.0.0", "description": "Two", "download": "plugins/plugin-two"},
            },
        }

        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:updates",
                "_back",
                "_back",
            ],
        )

        class TrackingLoader:
            def __init__(self) -> None:
                self._plugins: dict[str, Plugin] = {}

            def get_all_plugins(self) -> dict[str, Plugin]:
                return self._plugins

            def register(self, plugin: Plugin) -> None:
                self._plugins[plugin.info.name] = plugin

        loader = TrackingLoader()
        loader.register(SettingsPlugin())
        loader.register(PluginsPlugin())
        loader.register(FakePlugin1())  # type: ignore[arg-type]
        loader.register(FakePlugin2())  # type: ignore[arg-type]
        ctx._loader = loader  # type: ignore[attr-defined]

        plugin = PluginsPlugin()

        with patch.object(plugin, "_fetch_repo_index", return_value=mock_index):
            plugin.run(ctx)

        update_menus = [c for c in backend.captures if c.prompt == "Updates Available"]
        assert len(update_menus) == 1

        # Should have "Update All" option
        update_all_items = [i for i in update_menus[0].items if i.id == "plugins:update:all"]
        assert len(update_all_items) == 1
        assert "2 plugins" in update_all_items[0].badge


class TestUpdateSinglePlugin:
    """Tests for updating a single plugin."""

    def test_update_single_plugin_success(
        self, temp_dir: Path, sandbox_environment: Path
    ) -> None:
        """Successfully updates a single plugin."""
        from unittest.mock import MagicMock

        from menu_kit.plugins.base import PluginInfo

        # Create plugin directory in sandboxed location
        data_dir = sandbox_environment / "data"
        plugins_dir = data_dir / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        test_plugin_dir = plugins_dir / "test-plugin"
        test_plugin_dir.mkdir(exist_ok=True)
        (test_plugin_dir / "__init__.py").write_text('"""Old version."""\n')

        class FakePlugin:
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name="test-plugin", version="1.0.0")

        mock_index = {
            "version": 1,
            "plugins": {
                "test-plugin": {
                    "version": "2.0.0",
                    "description": "Test plugin",
                    "download": "plugins/test-plugin",
                },
            },
        }

        ctx, backend = create_context(
            temp_dir,
            [
                "plugins:updates",
                "plugins:update:test-plugin",  # Select plugin to update
                "_done",  # Dismiss result screen
                "_back",  # Back (updates menu is empty now)
            ],
        )

        class TrackingLoader:
            def __init__(self) -> None:
                self._plugins: dict[str, Plugin] = {}

            def get_all_plugins(self) -> dict[str, Plugin]:
                return self._plugins

            def register(self, plugin: Plugin) -> None:
                self._plugins[plugin.info.name] = plugin

            def unregister_plugin(self, name: str) -> bool:
                if name in self._plugins:
                    del self._plugins[name]
                    return True
                return False

        loader = TrackingLoader()
        loader.register(SettingsPlugin())
        loader.register(PluginsPlugin())
        loader.register(FakePlugin())  # type: ignore[arg-type]
        ctx._loader = loader  # type: ignore[attr-defined]

        plugin = PluginsPlugin()

        mock_content = b'"""New version 2.0.0."""\n\ndef create_plugin(): pass\n'

        with (
            patch.object(plugin, "_fetch_repo_index", return_value=mock_index),
            patch("menu_kit.plugins.builtin.plugins.urllib.request.urlopen") as mock_urlopen,
        ):
            mock_response = MagicMock()
            mock_response.read.return_value = mock_content
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with contextlib.suppress(MenuCancelled):
                plugin.run(ctx)

        # Verify success message was shown
        result_menus = [c for c in backend.captures if c.prompt == "Update Plugin"]
        assert len(result_menus) == 1
        messages = [i.title.lower() for i in result_menus[0].items]
        assert any("updated" in m and "success" in m for m in messages)

        # Verify plugin was reinstalled
        assert test_plugin_dir.exists()
        content = (test_plugin_dir / "__init__.py").read_text()
        assert "New version" in content
