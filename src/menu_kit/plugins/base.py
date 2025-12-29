"""Base plugin interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from menu_kit.core.database import ItemType, MenuItem

if TYPE_CHECKING:
    from menu_kit.core.config import Config
    from menu_kit.core.database import Database
    from menu_kit.menu.base import MenuBackend
    from menu_kit.plugins.loader import PluginLoader


# Sentinel for back navigation
BACK_SELECTED = object()


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
            Selected MenuItem, or None if cancelled/back selected
        """
        display_items = list(items)

        # Add back button at the bottom if enabled
        if show_back:
            back_item = MenuItem(
                id="_back",
                title="Back",
                item_type=ItemType.ACTION,
            )
            display_items.append(back_item)

        result = self.menu_backend.show(display_items, prompt)

        if result.cancelled:
            return None

        if result.selected and result.selected.id == "_back":
            return None

        return result.selected

    def notify(self, message: str) -> None:
        """Show a notification to the user."""
        # TODO: Implement notification system
        print(f"[notify] {message}")

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
    @abstractmethod
    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        ...

    def setup(self, ctx: PluginContext) -> None:  # noqa: B027
        """Called once when plugin is loaded. Optional override."""

    def teardown(self, ctx: PluginContext) -> None:  # noqa: B027
        """Called when plugin is unloaded. Optional override."""

    @abstractmethod
    def run(self, ctx: PluginContext, action: str = "") -> None:
        """Called when user selects this plugin.

        Args:
            ctx: Plugin context for accessing core functionality
            action: Sub-action if invoked via -p plugin:action
        """
        ...

    def index(self, ctx: PluginContext) -> list[MenuItem]:
        """Return items to add to main menu.

        Called on cache rebuild. Plugins can register multiple items.
        """
        return []
