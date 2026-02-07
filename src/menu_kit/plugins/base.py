"""Base plugin interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from menu_kit.core.database import ItemType, MenuItem

if TYPE_CHECKING:
    from menu_kit.core.config import Config
    from menu_kit.core.database import Database
    from menu_kit.menu.base import MenuBackend
    from menu_kit.plugins.loader import PluginLoader


class ActionResult(Enum):
    """Flow control signal returned by plugin actions.

    Plugins return this from run() to tell the runner what to do next:
    - CLOSE: Action completed, close the entire menu (launcher behaviour).
    - BACK: Go back to the previous menu level.
    """

    CLOSE = "close"
    BACK = "back"


# Sentinel for back navigation
BACK_SELECTED = object()


class MenuCancelled(Exception):
    """Raised when user presses ESC in a menu.

    ESC means "close the entire menu". This propagates up through the plugin
    to the loader, which catches it and returns ActionResult.CLOSE.

    Plugins should NOT catch this unless they need custom ESC handling.
    Use the Back menu item (returned as None from ctx.menu()) for navigation.
    """


@dataclass
class PluginContext:
    """Context passed to plugins, providing access to core functionality."""

    config: Config
    database: Database
    menu_backend: MenuBackend

    def menu(
        self,
        items: list[MenuItem],
        prompt: str = "",
        show_back: bool = True,
    ) -> MenuItem | None:
        """Show a menu and return the selected item.

        Args:
            items: Menu items to display
            prompt: Menu prompt text
            show_back: Whether to show a back button (default True)

        Returns:
            Selected MenuItem, or None if Back selected.

        Raises:
            MenuCancelled: If user presses ESC (closes entire menu).
        """
        display_items = list(items)
        selected_row: int | None = None

        if show_back:
            back_item = MenuItem(
                id="_back",
                title="Back",
                item_type=ItemType.ACTION,
            )
            if self.menu_backend.supports_selected_row:
                # Back at top, highlight first real item
                display_items.insert(0, back_item)
                selected_row = min(1, len(display_items) - 1)
            else:
                # Back at second position (one press up from default)
                pos = min(1, len(display_items))
                display_items.insert(pos, back_item)

        result = self.menu_backend.show(
            display_items, prompt, selected_row=selected_row
        )

        # ESC closes the entire menu
        if result.cancelled:
            raise MenuCancelled()

        if result.selected and result.selected.id == "_back":
            return None

        return result.selected

    def notify(self, message: str, title: str = "menu-kit") -> None:
        """Show a notification to the user.

        Uses notify-send for desktop notifications on Linux.
        Falls back to printing if notify-send is unavailable.
        """
        import shutil
        import subprocess

        if shutil.which("notify-send"):
            try:
                subprocess.run(
                    ["notify-send", title, message],
                    check=False,
                    capture_output=True,
                )
                return
            except OSError:
                pass
        # Fallback to console
        print(f"[{title}] {message}")

    def show_result(self, message: str, prompt: str = "Result") -> None:
        """Show an action result in a menu.

        Displays a message with a Done button. Use this for feedback
        after completing an action, keeping the user in the menu flow.

        Args:
            message: The result message to display
            prompt: The menu prompt/title
        """
        items = [
            MenuItem(
                id="_result_message",
                title=message,
                item_type=ItemType.INFO,
            ),
            MenuItem(
                id="_done",
                title="Done",
                item_type=ItemType.ACTION,
            ),
        ]
        # Show without back button since Done serves that purpose
        self.menu_backend.show(items, prompt)

    def get_data(self, key: str) -> Any:
        """Get plugin-specific data from storage."""
        # Plugin name will be set by the loader
        plugin_name = getattr(self, "_plugin_name", "unknown")
        return self.database.get_plugin_data(plugin_name, key)

    def set_data(self, key: str, value: Any) -> None:
        """Set plugin-specific data in storage."""
        plugin_name = getattr(self, "_plugin_name", "unknown")
        self.database.set_plugin_data(plugin_name, key, value)

    def register_items(self, items: list[MenuItem]) -> None:
        """Register items to appear in the main menu."""
        self.database.add_items(items)

    def get_installed_plugins(self) -> dict[str, PluginInfo]:
        """Get all installed plugins with their info."""
        loader: PluginLoader | None = getattr(self, "_loader", None)
        if loader is None:
            return {}
        return {name: plugin.info for name, plugin in loader.get_all_plugins().items()}

    def unregister_plugin(self, name: str) -> bool:
        """Unregister a plugin from the loader.

        This removes the plugin from the active plugins list, typically
        called after uninstalling a plugin.

        Returns:
            True if plugin was found and removed, False otherwise.
        """
        loader: PluginLoader | None = getattr(self, "_loader", None)
        if loader is None:
            return False
        return loader.unregister_plugin(name)


@dataclass
class PluginInfo:
    """Metadata about a plugin."""

    name: str
    version: str = "0.0.0"
    description: str = ""
    api_version: str = "1"
    author: str = ""
    dependencies: dict[str, Any] = field(default_factory=dict)


class Plugin(ABC):
    """Base plugin interface."""

    @property
    def cacheable(self) -> bool:
        """Whether plugin items can be cached.

        Cacheable plugins have their index() called during --rebuild and
        results stored in the database/display cache.

        Non-cacheable plugins have index() called at runtime for fresh data.
        Use cacheable=False for plugins with dynamic content (settings, plugin manager).

        Default: True
        """
        return True

    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        ...

    def setup(self, ctx: PluginContext) -> None:  # noqa: B027
        """Called once when plugin is loaded. Optional override."""

    def teardown(self, ctx: PluginContext) -> None:  # noqa: B027
        """Called when plugin is unloaded. Optional override."""

    @abstractmethod
    def run(self, ctx: PluginContext, action: str = "") -> ActionResult | None:
        """Called when user selects this plugin.

        Args:
            ctx: Plugin context for accessing core functionality
            action: Sub-action if invoked via -p plugin:action

        Returns:
            ActionResult controlling menu flow:
            - CLOSE: action completed, close the entire menu
            - BACK: go back to the previous menu level
            - None: treated as CLOSE (backwards compatible default)
        """
        ...

    def index(self, ctx: PluginContext) -> list[MenuItem]:
        """Return items to add to main menu.

        Called on cache rebuild. Plugins can register multiple items.
        """
        return []
