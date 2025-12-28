"""Settings plugin for configuring menu-kit."""

from __future__ import annotations

from menu_kit.core.database import ItemType, MenuItem
from menu_kit.plugins.base import Plugin, PluginContext, PluginInfo


class SettingsPlugin(Plugin):
    """Plugin for configuring menu-kit options."""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="settings",
            version="0.0.1",
            description="Configure menu-kit options",
        )

    def run(self, ctx: PluginContext, action: str = "") -> None:
        """Show settings menu."""
        items = [
            MenuItem(
                id="settings:frequency",
                title="Frequency Tracking",
                item_type=ItemType.ACTION,
                badge="On" if ctx.config.frequency_tracking else "Off",
            ),
            MenuItem(
                id="settings:backend",
                title="Menu Backend",
                item_type=ItemType.ACTION,
                badge=ctx.config.menu.backend or "auto",
            ),
            MenuItem(
                id="settings:rebuild",
                title="Rebuild Cache",
                item_type=ItemType.ACTION,
            ),
        ]

        selected = ctx.menu(items, prompt="Settings")
        if selected is None:
            return

        if selected.id == "settings:rebuild":
            ctx.notify("Cache rebuild not yet implemented")
        elif selected.id == "settings:frequency":
            ctx.notify("Toggle frequency tracking not yet implemented")
        elif selected.id == "settings:backend":
            ctx.notify("Backend selection not yet implemented")

    def index(self, ctx: PluginContext) -> list[MenuItem]:
        """Register settings in main menu."""
        return [
            MenuItem(
                id="settings",
                title="Settings",
                item_type=ItemType.SUBMENU,
                plugin="settings",
            ),
        ]


def create_plugin() -> Plugin:
    """Factory function to create the plugin."""
    return SettingsPlugin()
