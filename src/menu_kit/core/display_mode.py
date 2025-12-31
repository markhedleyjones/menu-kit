"""Display mode management for plugins."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from menu_kit.core.config import Config
    from menu_kit.core.database import Database


class DisplayMode(Enum):
    """Display mode for plugin items."""

    INLINE = "inline"
    SUBMENU = "submenu"


# Reserved plugin name for storing core preferences
CORE_PLUGIN_NAME = "_core"
DISPLAY_MODES_KEY = "display_modes"


class DisplayModeManager:
    """Manages plugin display mode preferences."""

    def __init__(self, config: Config, database: Database) -> None:
        self.config = config
        self.database = database
        self._cache: dict[str, DisplayMode] | None = None

    def get_mode(self, plugin_name: str) -> DisplayMode:
        """Get display mode for a plugin."""
        if self._cache is None:
            self._load_cache()

        assert self._cache is not None

        if plugin_name in self._cache:
            return self._cache[plugin_name]

        # Apply default logic
        return self._get_default_mode(plugin_name)

    def set_mode(self, plugin_name: str, mode: DisplayMode) -> None:
        """Set display mode for a plugin."""
        modes = self.database.get_plugin_data(CORE_PLUGIN_NAME, DISPLAY_MODES_KEY) or {}
        modes[plugin_name] = mode.value
        self.database.set_plugin_data(CORE_PLUGIN_NAME, DISPLAY_MODES_KEY, modes)
        self._cache = None  # Invalidate cache

    def _load_cache(self) -> None:
        """Load display modes from database."""
        stored = self.database.get_plugin_data(CORE_PLUGIN_NAME, DISPLAY_MODES_KEY) or {}
        self._cache = {name: DisplayMode(value) for name, value in stored.items()}

    def _get_default_mode(self, plugin_name: str) -> DisplayMode:
        """Calculate default mode based on config and item count."""
        default = self.config.plugins.default_display_mode

        if default == "inline":
            return DisplayMode.INLINE
        elif default == "submenu":
            return DisplayMode.SUBMENU

        # Auto mode: check item count
        counts = self.database.get_item_counts_by_plugin()
        count = counts.get(plugin_name, 0)
        threshold = self.config.plugins.item_threshold

        return DisplayMode.SUBMENU if count > threshold else DisplayMode.INLINE

    def format_inline_title(self, plugin_name: str, title: str) -> str:
        """Format a title with plugin prefix for inline display."""
        prefix = plugin_name.title()
        return f"{prefix}: {title}"
