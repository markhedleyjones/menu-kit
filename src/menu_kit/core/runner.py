"""Main orchestration for menu-kit."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from menu_kit.core.config import Config
from menu_kit.core.database import Database, MenuItem
from menu_kit.menu.base import get_backend
from menu_kit.plugins.loader import PluginLoader

if TYPE_CHECKING:
    from menu_kit.menu.base import MenuBackend


# Exit codes
EXIT_SUCCESS = 0
EXIT_CANCELLED = 1
EXIT_SELECTION_NOT_FOUND = 2
EXIT_PLUGIN_NOT_FOUND = 3
EXIT_EXECUTION_FAILED = 4
EXIT_CONFIG_ERROR = 5
EXIT_NO_BACKEND = 6


@dataclass
class RunnerOptions:
    """Options for the runner."""

    backend: str | None = None
    backend_args: str | None = None
    terminal: bool = False
    print_items: bool = False
    dry_run: bool = False
    rebuild: bool = False
    plugin: str | None = None
    selections: list[str] | None = None


class Runner:
    """Main orchestration class for menu-kit."""

    def __init__(self, options: RunnerOptions | None = None) -> None:
        self.options = options or RunnerOptions()
        self.config: Config | None = None
        self.database: Database | None = None
        self.backend: MenuBackend | None = None
        self.loader: PluginLoader | None = None

    def setup(self) -> int:
        """Initialize all components. Returns exit code."""
        # Load config
        self.config = Config.load()

        # Initialize database
        self.database = Database()

        # Determine backend
        backend_name = self.options.backend
        if self.options.terminal:
            backend_name = "fzf"
        elif self.options.print_items:
            backend_name = "stdout"
        elif not backend_name:
            backend_name = self.config.menu.backend or None

        self.backend = get_backend(backend_name)
        if self.backend is None:
            print("Error: No menu backend available", file=sys.stderr)
            return EXIT_NO_BACKEND

        # Load plugins
        self.loader = PluginLoader(self.config, self.database, self.backend)
        self.loader.load_all()

        # Rebuild index
        self.loader.index_all()

        return EXIT_SUCCESS

    def run(self) -> int:
        """Run the main loop. Returns exit code."""
        setup_code = self.setup()
        if setup_code != EXIT_SUCCESS:
            return setup_code

        assert self.config is not None
        assert self.database is not None
        assert self.backend is not None
        assert self.loader is not None

        # Handle rebuild
        if self.options.rebuild:
            self.loader.index_all()
            print("Cache rebuilt")
            return EXIT_SUCCESS

        # Handle direct plugin invocation
        if self.options.plugin:
            return self._run_plugin(self.options.plugin)

        # Handle chained selections
        if self.options.selections:
            return self._run_selections(self.options.selections)

        # Handle print mode
        if self.options.print_items:
            return self._print_items()

        # Normal menu mode
        return self._run_menu()

    def _run_plugin(self, plugin_spec: str) -> int:
        """Run a plugin directly."""
        assert self.loader is not None

        # Parse plugin:action format
        if ":" in plugin_spec:
            plugin_name, action = plugin_spec.split(":", 1)
        else:
            plugin_name = plugin_spec
            action = ""

        if self.options.dry_run:
            print(f"Would run plugin: {plugin_name}")
            if action:
                print(f"With action: {action}")
            return EXIT_SUCCESS

        if not self.loader.run_plugin(plugin_name, action):
            print(f"Plugin not found: {plugin_name}", file=sys.stderr)
            return EXIT_PLUGIN_NOT_FOUND

        return EXIT_SUCCESS

    def _run_selections(self, selections: list[str]) -> int:
        """Run through chained selections."""
        assert self.database is not None
        assert self.config is not None
        assert self.loader is not None

        prefix = self.config.display.submenu_prefix

        for selection in selections:
            # Find matching item
            item = self.database.find_item_by_title(selection, prefix)

            if item is None:
                print(f"Selection not found: {selection}", file=sys.stderr)
                return EXIT_SELECTION_NOT_FOUND

            if self.options.dry_run:
                print(f"Would select: {item.title}")
                continue

            # Execute the item
            if item.plugin:
                # Parse action from item ID if present
                action = ""
                if ":" in item.id:
                    _, action = item.id.split(":", 1)
                self.loader.run_plugin(item.plugin, action)

        return EXIT_SUCCESS

    def _print_items(self) -> int:
        """Print all items to stdout."""
        assert self.database is not None
        assert self.config is not None

        items = self.database.get_items(order_by_frequency=True)
        prefix = self.config.display.submenu_prefix

        for item in items:
            display = self._format_item(item, prefix)
            print(display)

        return EXIT_SUCCESS

    def _run_menu(self) -> int:
        """Run the interactive menu loop."""
        assert self.database is not None
        assert self.backend is not None
        assert self.config is not None
        assert self.loader is not None

        while True:
            items = self.database.get_items(order_by_frequency=True)

            if not items:
                print("No items in menu. Install plugins with: menu-kit -p plugins")
                return EXIT_CANCELLED

            result = self.backend.show(items, prompt="menu-kit")

            # Exit only when cancelled from main menu
            if result.cancelled or result.selected is None:
                return EXIT_CANCELLED

            item = result.selected

            # Record usage
            if self.config.frequency_tracking:
                self.database.record_use(item.id)

            # Execute plugin and loop back to main menu
            if item.plugin:
                action = ""
                if ":" in item.id:
                    _, action = item.id.split(":", 1)
                self.loader.run_plugin(item.plugin, action)

    def _format_item(self, item: MenuItem, prefix: str) -> str:
        """Format an item for display."""
        from menu_kit.core.database import ItemType

        display = item.title
        if item.item_type == ItemType.SUBMENU:
            display = f"{prefix}{display}"
        if item.badge:
            display = f"{display}  ({item.badge})"
        return display

    def teardown(self) -> None:
        """Clean up resources."""
        if self.loader:
            self.loader.teardown_all()
