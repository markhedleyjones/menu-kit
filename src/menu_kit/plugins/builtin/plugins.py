"""Plugins plugin for browsing and managing plugins."""

from __future__ import annotations

from menu_kit.core.database import ItemType, MenuItem
from menu_kit.core.display_mode import DisplayMode, DisplayModeManager
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
            installed_count = len(ctx.get_installed_plugins())
            items = [
                MenuItem(
                    id="plugins:installed",
                    title="Installed",
                    item_type=ItemType.SUBMENU,
                    badge=str(installed_count),
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
        display_manager = DisplayModeManager(ctx.config, ctx.database)

        while True:
            installed = ctx.get_installed_plugins()
            items = []

            for name, info in sorted(installed.items()):
                # Get display mode for this plugin
                mode = display_manager.get_mode(name)
                mode_label = mode.value

                # Determine if bundled
                bundled_plugins = {"settings", "plugins"}
                source = "bundled" if name in bundled_plugins else "installed"

                badge = f"{info.version} ({source}) | {mode_label}"

                items.append(
                    MenuItem(
                        id=f"plugins:info:{name}",
                        title=name,
                        item_type=ItemType.ACTION,
                        badge=badge,
                    )
                )

            selected = ctx.menu(items, prompt="Installed Plugins")
            if selected is None:
                return

            # Extract plugin name from ID
            plugin_name = selected.id.replace("plugins:info:", "")
            self._show_plugin_options(ctx, plugin_name, display_manager)

    def _show_plugin_options(
        self,
        ctx: PluginContext,
        plugin_name: str,
        display_manager: DisplayModeManager,
    ) -> None:
        """Show options for a specific plugin."""
        installed = ctx.get_installed_plugins()
        info = installed.get(plugin_name)
        if info is None:
            return

        while True:
            current_mode = display_manager.get_mode(plugin_name)

            # Build toggle label
            if current_mode == DisplayMode.INLINE:
                toggle_label = "Change to Submenu"
                toggle_badge = "currently inline"
            else:
                toggle_label = "Change to Inline"
                toggle_badge = "currently submenu"

            items = [
                MenuItem(
                    id=f"plugins:opt:{plugin_name}:info",
                    title="Info",
                    item_type=ItemType.INFO,
                    badge=f"v{info.version}",
                ),
                MenuItem(
                    id=f"plugins:opt:{plugin_name}:toggle",
                    title=toggle_label,
                    item_type=ItemType.ACTION,
                    badge=toggle_badge,
                ),
            ]

            # Add uninstall option for non-bundled plugins
            bundled_plugins = {"settings", "plugins"}
            if plugin_name not in bundled_plugins:
                items.append(
                    MenuItem(
                        id=f"plugins:opt:{plugin_name}:uninstall",
                        title="Uninstall",
                        item_type=ItemType.ACTION,
                    )
                )

            selected = ctx.menu(items, prompt=plugin_name.title())
            if selected is None:
                return

            if selected.id.endswith(":toggle"):
                # Toggle display mode
                new_mode = (
                    DisplayMode.SUBMENU
                    if current_mode == DisplayMode.INLINE
                    else DisplayMode.INLINE
                )
                display_manager.set_mode(plugin_name, new_mode)
                ctx.notify(f"Display mode changed to {new_mode.value}")
            elif selected.id.endswith(":uninstall"):
                ctx.notify("Uninstall not yet implemented")

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
