"""Main orchestration for menu-kit."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from menu_kit.core.config import Config
from menu_kit.core.database import Database, ItemType, MenuItem
from menu_kit.core.display_mode import DisplayMode, DisplayModeManager
from menu_kit.menu.base import GUI_BACKENDS, get_backend
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
            print(
                "Install one of: rofi, dmenu, fuzzel (GUI) or fzf (terminal)",
                file=sys.stderr,
            )
            return EXIT_NO_BACKEND

        # Warn if using terminal backend without explicit request
        if (
            self.backend.name not in GUI_BACKENDS
            and not self.options.terminal
            and not self.options.print_items
            and not backend_name
        ):
            print(
                f"Warning: Using terminal backend '{self.backend.name}'. "
                "Install rofi, dmenu, or fuzzel for GUI mode.",
                file=sys.stderr,
            )

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

        display_manager = DisplayModeManager(self.config, self.database)
        items = self._build_main_menu(display_manager)
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

        display_manager = DisplayModeManager(self.config, self.database)

        while True:
            items = self._build_main_menu(display_manager)

            if not items:
                print("No items in menu. Install plugins with: menu-kit -p plugins")
                return EXIT_CANCELLED

            result = self.backend.show(items, prompt="menu-kit")

            # Exit only when cancelled from main menu
            if result.cancelled or result.selected is None:
                return EXIT_CANCELLED

            item = result.selected

            # Handle submenu entry selection
            if item.id.startswith("_submenu:"):
                plugin_name = item.id[9:]  # Remove "_submenu:" prefix
                if self._show_plugin_submenu(plugin_name, display_manager):
                    return EXIT_SUCCESS  # Plugin was executed, exit
                continue

            # Record usage
            if self.config.frequency_tracking:
                self.database.record_use(item.id)

            # Execute plugin and exit (launcher behavior)
            if item.plugin:
                action = ""
                if ":" in item.id:
                    _, action = item.id.split(":", 1)
                self.loader.run_plugin(item.plugin, action)
                return EXIT_SUCCESS

    def _build_main_menu(self, display_manager: DisplayModeManager) -> list[MenuItem]:
        """Build the main menu respecting display modes."""
        assert self.database is not None
        assert self.loader is not None
        assert self.config is not None

        sort = self.config.display.sort
        order_by_freq = sort == "frequency"
        all_items = self.database.get_items(order_by_frequency=order_by_freq)

        result: list[MenuItem] = []
        submenu_plugins: dict[str, int] = {}  # plugin_name -> item_count

        for item in all_items:
            if not item.plugin:
                result.append(item)
                continue

            # SUBMENU items always show as submenus (e.g., Settings, Plugins, Files)
            if item.item_type == ItemType.SUBMENU:
                result.append(item)
                continue

            mode = display_manager.get_mode(item.plugin)

            if mode == DisplayMode.INLINE:
                # Create new item with prefixed title (don't mutate original)
                result.append(
                    MenuItem(
                        id=item.id,
                        title=display_manager.format_inline_title(
                            item.plugin, item.title
                        ),
                        item_type=item.item_type,
                        path=item.path,
                        plugin=item.plugin,
                        metadata=item.metadata,
                        icon=item.icon,
                        badge=item.badge,
                        use_count=item.use_count,
                        last_used=item.last_used,
                    )
                )
            else:
                # Track plugin for submenu entry
                submenu_plugins[item.plugin] = submenu_plugins.get(item.plugin, 0) + 1

        # Add submenu entries for plugins in submenu mode
        for plugin_name, count in submenu_plugins.items():
            plugin = self.loader.get_plugin(plugin_name)
            title = plugin.info.name.title() if plugin else plugin_name.title()

            result.append(
                MenuItem(
                    id=f"_submenu:{plugin_name}",
                    title=title,
                    item_type=ItemType.SUBMENU,
                    plugin=plugin_name,
                    badge=f"{count} items",
                )
            )

        # Apply sorting
        result = self._sort_menu_items(result, sort)

        # Put submenus first if configured
        if self.config.display.submenus_first:
            submenus = [i for i in result if i.item_type == ItemType.SUBMENU]
            others = [i for i in result if i.item_type != ItemType.SUBMENU]
            result = submenus + others

        return result

    def _sort_menu_items(self, items: list[MenuItem], sort: str) -> list[MenuItem]:
        """Sort menu items according to the configured mode."""
        if sort == "frequency":
            # Already sorted by frequency from database query
            return items
        elif sort == "alpha":
            return sorted(items, key=lambda x: x.title.lower())
        elif sort == "length":
            # Sort by title length, then alphabetically
            return sorted(items, key=lambda x: (len(x.title), x.title.lower()))
        else:
            return items

    def _show_plugin_submenu(
        self, plugin_name: str, display_manager: DisplayModeManager
    ) -> bool:
        """Show items for a plugin in submenu mode.

        Returns:
            True if a plugin was executed (caller should exit),
            False if cancelled/back (caller should continue).
        """
        assert self.database is not None
        assert self.backend is not None
        assert self.config is not None
        assert self.loader is not None

        plugin = self.loader.get_plugin(plugin_name)
        prompt = plugin.info.name.title() if plugin else plugin_name.title()

        while True:
            items = self.database.get_items(plugin=plugin_name, order_by_frequency=True)

            if not items:
                return False

            # Add back button
            items.append(MenuItem(id="_back", title="Back", item_type=ItemType.ACTION))

            result = self.backend.show(items, prompt=prompt)

            if result.cancelled or result.selected is None:
                return False

            if result.selected.id == "_back":
                return False

            item = result.selected

            # Record usage
            if self.config.frequency_tracking:
                self.database.record_use(item.id)

            # Execute and exit
            if item.plugin:
                action = ""
                if ":" in item.id:
                    _, action = item.id.split(":", 1)
                self.loader.run_plugin(item.plugin, action)
                return True  # Signal to exit menu

            return False

    def _format_item(self, item: MenuItem, prefix: str) -> str:
        """Format an item for display."""
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
