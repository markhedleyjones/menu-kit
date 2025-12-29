"""Plugins plugin for browsing and managing plugins."""

from __future__ import annotations

import json
import shutil
import urllib.request
from typing import Any

from menu_kit.core.config import get_data_dir
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
                if self._uninstall_plugin(ctx, plugin_name):
                    ctx.notify(f"Uninstalled {plugin_name}")
                    return  # Go back to installed list
                else:
                    ctx.notify(f"Failed to uninstall {plugin_name}")

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
                repo = selected.id.replace("plugins:repo:", "")
                self._show_repo_plugins(ctx, repo)

    def _fetch_repo_index(self, repo: str) -> dict[str, Any] | None:
        """Fetch index.json from a GitHub repository."""
        url = f"https://raw.githubusercontent.com/{repo}/main/index.json"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

    def _show_repo_plugins(self, ctx: PluginContext, repo: str) -> None:
        """Show plugins available in a repository."""
        index = self._fetch_repo_index(repo)
        if index is None:
            ctx.notify(f"Failed to fetch plugins from {repo}")
            return

        installed = ctx.get_installed_plugins()

        while True:
            items = []
            plugins = index.get("plugins", {})

            for name, info in sorted(plugins.items()):
                is_installed = name in installed
                badge = f"v{info.get('version', '?')}"
                if is_installed:
                    badge += " (installed)"

                items.append(
                    MenuItem(
                        id=f"plugins:available:{repo}:{name}",
                        title=name,
                        item_type=ItemType.ACTION,
                        badge=badge,
                        metadata={"repo": repo, "info": info},
                    )
                )

            if not items:
                items.append(
                    MenuItem(
                        id="plugins:browse:empty",
                        title="No plugins available",
                        item_type=ItemType.INFO,
                    )
                )

            title = "Official" if repo == self.OFFICIAL_REPO else repo
            selected = ctx.menu(items, prompt=title)
            if selected is None:
                return

            if selected.id.startswith("plugins:available:"):
                parts = selected.id.split(":", 3)
                plugin_name = parts[3]
                plugin_info = plugins.get(plugin_name, {})
                self._show_plugin_install_options(
                    ctx, repo, plugin_name, plugin_info, plugin_name in installed
                )

    def _show_plugin_install_options(
        self,
        ctx: PluginContext,
        repo: str,
        plugin_name: str,
        plugin_info: dict[str, Any],
        is_installed: bool,
    ) -> None:
        """Show install/info options for a plugin."""
        while True:
            items = [
                MenuItem(
                    id=f"plugins:detail:{plugin_name}:desc",
                    title=plugin_info.get("description", "No description"),
                    item_type=ItemType.INFO,
                ),
            ]

            if is_installed:
                items.append(
                    MenuItem(
                        id=f"plugins:detail:{plugin_name}:installed",
                        title="Already installed",
                        item_type=ItemType.INFO,
                    )
                )
            else:
                items.append(
                    MenuItem(
                        id=f"plugins:detail:{plugin_name}:install",
                        title="Install",
                        item_type=ItemType.ACTION,
                    )
                )

            selected = ctx.menu(items, prompt=plugin_name.title())
            if selected is None:
                return

            if selected.id.endswith(":install"):
                if self._install_plugin(ctx, repo, plugin_name, plugin_info):
                    ctx.notify(f"Installed {plugin_name}")
                    return
                else:
                    ctx.notify(f"Failed to install {plugin_name}")

    def _install_plugin(
        self,
        ctx: PluginContext,
        repo: str,
        plugin_name: str,
        plugin_info: dict[str, Any],
    ) -> bool:
        """Download and install a plugin from a repository."""
        plugins_dir = get_data_dir() / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)

        target_dir = plugins_dir / plugin_name
        if target_dir.exists():
            return False  # Already exists

        # Get download path from index
        download_path = plugin_info.get("download", f"plugins/{plugin_name}")

        # Download __init__.py (main plugin file)
        base_url = f"https://raw.githubusercontent.com/{repo}/main/{download_path}"
        init_url = f"{base_url}/__init__.py"

        try:
            # Create plugin directory
            target_dir.mkdir(parents=True, exist_ok=True)

            # Download main file
            init_path = target_dir / "__init__.py"
            with urllib.request.urlopen(init_url, timeout=30) as response:
                init_path.write_bytes(response.read())

            return True
        except Exception:
            # Clean up on failure
            if target_dir.exists():
                shutil.rmtree(target_dir)
            return False

    def _uninstall_plugin(self, ctx: PluginContext, plugin_name: str) -> bool:
        """Uninstall a plugin by removing its directory."""
        plugins_dir = get_data_dir() / "plugins"
        target_dir = plugins_dir / plugin_name

        # Also check for symlinks
        if target_dir.is_symlink():
            target_dir.unlink()
            # Clear items from database
            ctx.database.delete_items_by_plugin(plugin_name)
            return True

        if target_dir.exists() and target_dir.is_dir():
            shutil.rmtree(target_dir)
            # Clear items from database
            ctx.database.delete_items_by_plugin(plugin_name)
            return True

        return False

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
