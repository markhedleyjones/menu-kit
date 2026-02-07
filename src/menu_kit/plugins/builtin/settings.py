"""Settings plugin for configuring menu-kit."""

from __future__ import annotations

from menu_kit.core.database import ItemType, MenuItem
from menu_kit.plugins.base import ActionResult, Plugin, PluginContext, PluginInfo

# Available backends (in priority order)
BACKENDS = ["auto", "rofi", "dmenu", "fuzzel", "fzf"]


class SettingsPlugin(Plugin):
    """Plugin for configuring menu-kit options."""

    @property
    def cacheable(self) -> bool:
        """Settings is always computed fresh - cheap and ensures availability."""
        return False

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="settings",
            version="0.0.1",
            description="Configure menu-kit options",
        )

    def run(self, ctx: PluginContext, action: str = "") -> ActionResult:
        """Show settings menu."""
        while True:
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
                    item_type=ItemType.SUBMENU,
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
                return ActionResult.BACK

            if selected.id == "settings:rebuild":
                self._rebuild_cache(ctx)
                return ActionResult.CLOSE
            elif selected.id == "settings:frequency":
                self._toggle_frequency(ctx)
                return ActionResult.CLOSE
            elif selected.id == "settings:backend":
                result = self._select_backend(ctx)
                if result == ActionResult.CLOSE:
                    return ActionResult.CLOSE
                # BACK from backend submenu: continue settings loop

    def _toggle_frequency(self, ctx: PluginContext) -> None:
        """Toggle frequency tracking on/off."""
        ctx.config.frequency_tracking = not ctx.config.frequency_tracking
        ctx.config.save()
        state = "enabled" if ctx.config.frequency_tracking else "disabled"
        ctx.notify(f"Frequency tracking {state}")

    def _select_backend(self, ctx: PluginContext) -> ActionResult:
        """Show backend selection submenu."""
        while True:
            current = ctx.config.menu.backend or "auto"
            items = []

            for backend in BACKENDS:
                badge = "✓" if backend == current else None
                items.append(
                    MenuItem(
                        id=f"settings:backend:{backend}",
                        title=backend,
                        item_type=ItemType.ACTION,
                        badge=badge,
                    )
                )

            selected = ctx.menu(items, prompt="Select Backend")
            if selected is None:
                return ActionResult.BACK

            # Extract backend name from ID
            backend = selected.id.split(":")[-1]
            ctx.config.menu.backend = "" if backend == "auto" else backend
            ctx.config.save()
            ctx.notify(f"Backend set to {backend}")
            return ActionResult.CLOSE

    def _rebuild_cache(self, ctx: PluginContext) -> None:
        """Trigger a cache rebuild."""
        # Get the loader to trigger a full reindex
        loader = getattr(ctx, "_loader", None)
        if loader is not None:
            loader.index_all()
            item_count = len(ctx.database.get_items())
            ctx.notify(f"Cache rebuilt ({item_count} items)")
        else:
            ctx.database.clear_items()
            ctx.notify("Cache cleared")

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
