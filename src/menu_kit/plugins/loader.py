"""Plugin discovery and loading."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from menu_kit.core.config import get_config_dir, get_data_dir
from menu_kit.plugins.base import Plugin, PluginContext

if TYPE_CHECKING:
    from menu_kit.core.config import Config
    from menu_kit.core.database import Database
    from menu_kit.menu.base import MenuBackend


class PluginLoader:
    """Discovers and loads plugins."""

    def __init__(
        self,
        config: Config,
        database: Database,
        menu_backend: MenuBackend,
    ) -> None:
        self.config = config
        self.database = database
        self.menu_backend = menu_backend
        self._plugins: dict[str, Plugin] = {}
        self._contexts: dict[str, PluginContext] = {}

    def load_all(self) -> dict[str, Plugin]:
        """Load all available plugins."""
        # Load built-in plugins first
        self._load_builtin_plugins()

        # Load user plugins from ~/.local/share/menu-kit/plugins/
        user_plugins_dir = get_data_dir() / "plugins"
        if user_plugins_dir.exists():
            self._load_plugins_from_dir(user_plugins_dir)

        # Load local plugins from ~/.config/menu-kit/plugins/
        local_plugins_dir = get_config_dir() / "plugins"
        if local_plugins_dir.exists():
            self._load_plugins_from_dir(local_plugins_dir)

        return self._plugins

    def _load_builtin_plugins(self) -> None:
        """Load built-in plugins."""
        from menu_kit.plugins.builtin import plugins, settings

        for module in [settings, plugins]:
            if hasattr(module, "create_plugin"):
                plugin = module.create_plugin()
                self._register_plugin(plugin)

    def _load_plugins_from_dir(self, directory: Path) -> None:
        """Load plugins from a directory."""
        for item in directory.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                # Package plugin
                self._load_plugin_package(item)
            elif (
                item.is_file()
                and item.suffix == ".py"
                and not item.name.startswith("_")
            ):
                # Single-file plugin
                self._load_plugin_file(item)

    def _load_plugin_package(self, package_dir: Path) -> None:
        """Load a plugin from a package directory."""
        try:
            spec = importlib.util.spec_from_file_location(
                package_dir.name,
                package_dir / "__init__.py",
                submodule_search_locations=[str(package_dir)],
            )
            if spec is None or spec.loader is None:
                return

            module = importlib.util.module_from_spec(spec)
            sys.modules[package_dir.name] = module
            spec.loader.exec_module(module)

            if hasattr(module, "create_plugin"):
                plugin = module.create_plugin()
                self._register_plugin(plugin)
        except Exception as e:
            print(f"Failed to load plugin from {package_dir}: {e}")

    def _load_plugin_file(self, file_path: Path) -> None:
        """Load a plugin from a single Python file."""
        try:
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                return

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            if hasattr(module, "create_plugin"):
                plugin = module.create_plugin()
                self._register_plugin(plugin)
        except Exception as e:
            print(f"Failed to load plugin from {file_path}: {e}")

    def _register_plugin(self, plugin: Plugin) -> None:
        """Register a loaded plugin."""
        name = plugin.info.name
        self._plugins[name] = plugin

        # Create context for this plugin
        ctx = PluginContext(
            config=self.config,
            database=self.database,
            menu_backend=self.menu_backend,
        )
        # Set the plugin name so context can scope data storage
        ctx._plugin_name = name  # type: ignore[attr-defined]
        # Set loader reference so context can list installed plugins
        ctx._loader = self  # type: ignore[attr-defined]
        self._contexts[name] = ctx

        # Call setup
        try:
            plugin.setup(ctx)
        except Exception as e:
            print(f"Failed to setup plugin {name}: {e}")

    def get_plugin(self, name: str) -> Plugin | None:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def get_context(self, name: str) -> PluginContext | None:
        """Get the context for a plugin."""
        return self._contexts.get(name)

    def get_all_plugins(self) -> dict[str, Plugin]:
        """Get all loaded plugins."""
        return self._plugins

    def run_plugin(self, name: str, action: str = "") -> bool:
        """Run a plugin by name.

        Args:
            name: Plugin name (may include :action suffix)
            action: Action to run (overrides suffix in name)

        Returns:
            True if plugin was found and run, False otherwise
        """
        # Parse plugin:action format
        if ":" in name and not action:
            name, action = name.split(":", 1)

        plugin = self.get_plugin(name)
        ctx = self.get_context(name)

        if plugin is None or ctx is None:
            return False

        try:
            plugin.run(ctx, action)
            return True
        except Exception as e:
            print(f"Error running plugin {name}: {e}")
            return False

    def index_all(self) -> None:
        """Rebuild the index from all plugins."""
        for name, plugin in self._plugins.items():
            ctx = self._contexts.get(name)
            if ctx is None:
                continue

            try:
                # Clear old items for this plugin
                self.database.delete_items_by_plugin(name)

                # Get new items
                items = plugin.index(ctx)

                # Tag items with plugin name
                for item in items:
                    item.plugin = name

                # Store items
                self.database.add_items(items)
            except Exception as e:
                print(f"Error indexing plugin {name}: {e}")

    def teardown_all(self) -> None:
        """Teardown all plugins."""
        for name, plugin in self._plugins.items():
            ctx = self._contexts.get(name)
            if ctx is None:
                continue

            try:
                plugin.teardown(ctx)
            except Exception as e:
                print(f"Error during teardown of plugin {name}: {e}")
