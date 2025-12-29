"""Plugins plugin for browsing and managing plugins."""

from __future__ import annotations

from menu_kit.core.database import ItemType, MenuItem
from menu_kit.plugins.base import Plugin, PluginContext, PluginInfo


class PluginsPlugin(Plugin):
    """Plugin for browsing, installing, and managing plugins."""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="plugins",
            version="0.0.1",
            description="Browse and manage plugins",
        )

    def run(self, ctx: PluginContext, action: str = "") -> None:
        """Show plugins menu."""
        if action == "installed":
            self._show_installed(ctx)
        elif action == "browse":
            self._show_browse(ctx)
        else:
            self._show_main_menu(ctx)

    def _show_main_menu(self, ctx: PluginContext) -> None:
        """Show main plugins menu."""
        while True:
            items = [
                MenuItem(
                    id="plugins:installed",
                    title="Installed",
                    item_type=ItemType.SUBMENU,
                    badge="2",  # TODO: actual count
                ),
                MenuItem(
                    id="plugins:browse",
                    title="Browse Plugins",
                    item_type=ItemType.SUBMENU,
                ),
                MenuItem(
                    id="plugins:updates",
                    title="Check for Updates",
                    item_type=ItemType.ACTION,
                ),
            ]

            selected = ctx.menu(items, prompt="Plugins")
            if selected is None:
                return

            if selected.id == "plugins:installed":
                self._show_installed(ctx)
            elif selected.id == "plugins:browse":
                self._show_browse(ctx)
            elif selected.id == "plugins:updates":
                ctx.notify("Update check not yet implemented")

    def _show_installed(self, ctx: PluginContext) -> None:
        """Show installed plugins."""
        while True:
            items = [
                MenuItem(
                    id="plugins:info:settings",
                    title="settings",
                    item_type=ItemType.ACTION,
                    badge="0.0.1 (bundled)",
                ),
                MenuItem(
                    id="plugins:info:plugins",
                    title="plugins",
                    item_type=ItemType.ACTION,
                    badge="0.0.1 (bundled)",
                ),
            ]

            selected = ctx.menu(items, prompt="Installed Plugins")
            if selected is None:
                return

            ctx.notify(f"Plugin info: {selected.title}")

    # Official repository identifier
    OFFICIAL_REPO = "markhedleyjones/menu-kit-plugins"

    def _show_browse(self, ctx: PluginContext) -> None:
        """Show available plugins for installation."""
        while True:
            items = [
                MenuItem(
                    id="plugins:browse:info",
                    title="Connect to repository to browse plugins",
                    item_type=ItemType.INFO,
                ),
            ]

            repos = ctx.config.plugins.repositories
            for repo in repos:
                # Show "Official" for the official repo, path for others
                title = "Official" if repo == self.OFFICIAL_REPO else repo
                items.append(
                    MenuItem(
                        id=f"plugins:repo:{repo}",
                        title=title,
                        item_type=ItemType.SUBMENU,
                    )
                )

            selected = ctx.menu(items, prompt="Browse Plugins")
            if selected is None:
                return

            if selected.id.startswith("plugins:repo:"):
                ctx.notify("Repository browsing not yet implemented")

    def index(self, ctx: PluginContext) -> list[MenuItem]:
        """Register plugins menu in main menu."""
        return [
            MenuItem(
                id="plugins",
                title="Plugins",
                item_type=ItemType.SUBMENU,
                plugin="plugins",
            ),
        ]


def create_plugin() -> Plugin:
    """Factory function to create the plugin."""
    return PluginsPlugin()
