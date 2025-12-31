"""Configuration management for menu-kit."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def get_config_dir() -> Path:
    """Get the configuration directory, respecting XDG."""
    xdg_config = Path.home() / ".config"
    return xdg_config / "menu-kit"


def get_cache_dir() -> Path:
    """Get the cache directory, respecting XDG."""
    xdg_cache = Path.home() / ".cache"
    return xdg_cache / "menu-kit"


def get_data_dir() -> Path:
    """Get the data directory, respecting XDG."""
    xdg_data = Path.home() / ".local" / "share"
    return xdg_data / "menu-kit"


@dataclass
class MenuBackendConfig:
    """Configuration for a menu backend."""

    args: list[str] = field(default_factory=list)


@dataclass
class MenuConfig:
    """Configuration for the menu system."""

    backend: str = ""  # Empty means auto-detect
    rofi: MenuBackendConfig = field(default_factory=MenuBackendConfig)
    fuzzel: MenuBackendConfig = field(default_factory=MenuBackendConfig)
    dmenu: MenuBackendConfig = field(default_factory=MenuBackendConfig)
    fzf: MenuBackendConfig = field(default_factory=MenuBackendConfig)


@dataclass
class DisplayConfig:
    """Configuration for display formatting."""

    submenu_prefix: str = "→ "
    info_prefix: str = ""
    header_prefix: str = ""
    separator: str = "─" * 40
    show_info_items: bool = True
    show_headers: bool = True
    show_separators: bool = True
    sort: str = "alpha"  # "alpha", "frequency", "length"
    submenus_first: bool = True


@dataclass
class PluginsConfig:
    """Configuration for the plugin system."""

    repositories: list[str] = field(default_factory=lambda: ["markhedleyjones/menu-kit-plugins"])
    allow_unverified: bool = False
    default_display_mode: str = "auto"  # "inline", "submenu", "auto"
    item_threshold: int = 20  # For auto mode: >threshold items → submenu


@dataclass
class Config:
    """Main configuration for menu-kit."""

    menu: MenuConfig = field(default_factory=MenuConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    frequency_tracking: bool = True
    _source_path: Path | None = field(default=None, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load configuration from file, falling back to defaults."""
        if path is None:
            path = get_config_dir() / "config.toml"

        if not path.exists():
            config = cls()
            config._source_path = path
            return config

        with path.open("rb") as f:
            data = tomllib.load(f)

        config = cls.from_dict(data)
        config._source_path = path
        return config

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """Create Config from a dictionary."""
        menu_data = data.get("menu", {})
        menu = MenuConfig(
            backend=menu_data.get("backend", ""),
            rofi=MenuBackendConfig(args=menu_data.get("rofi", {}).get("args", [])),
            fuzzel=MenuBackendConfig(args=menu_data.get("fuzzel", {}).get("args", [])),
            dmenu=MenuBackendConfig(args=menu_data.get("dmenu", {}).get("args", [])),
            fzf=MenuBackendConfig(args=menu_data.get("fzf", {}).get("args", [])),
        )

        display_data = data.get("display", {})
        display = DisplayConfig(
            submenu_prefix=display_data.get("submenu_prefix", "→ "),
            info_prefix=display_data.get("info_prefix", ""),
            header_prefix=display_data.get("header_prefix", ""),
            separator=display_data.get("separator", "─" * 40),
            show_info_items=display_data.get("show_info_items", True),
            show_headers=display_data.get("show_headers", True),
            show_separators=display_data.get("show_separators", True),
            sort=display_data.get("sort", "alpha"),
            submenus_first=display_data.get("submenus_first", True),
        )

        plugins_data = data.get("plugins", {})
        plugins = PluginsConfig(
            repositories=plugins_data.get("repositories", ["markhedleyjones/menu-kit-plugins"]),
            allow_unverified=plugins_data.get("allow_unverified", False),
            default_display_mode=plugins_data.get("default_display_mode", "auto"),
            item_threshold=plugins_data.get("item_threshold", 20),
        )

        return cls(
            menu=menu,
            display=display,
            plugins=plugins,
            frequency_tracking=data.get("frequency_tracking", True),
        )

    def get_backend_args(self, backend: str) -> list[str]:
        """Get arguments for a specific backend."""
        backend_config = getattr(self.menu, backend, None)
        if backend_config is None:
            return []
        if isinstance(backend_config, MenuBackendConfig):
            return backend_config.args
        return []

    def save(self, path: Path | None = None) -> None:
        """Save configuration to file."""
        if path is None:
            path = self._source_path or (get_config_dir() / "config.toml")

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = []

        # Root level settings
        lines.append(f"frequency_tracking = {str(self.frequency_tracking).lower()}")
        lines.append("")

        # Menu section
        lines.append("[menu]")
        if self.menu.backend:
            lines.append(f'backend = "{self.menu.backend}"')
        lines.append("")

        # Backend args (only if non-empty)
        for backend_name in ["rofi", "fuzzel", "dmenu", "fzf"]:
            backend_config = getattr(self.menu, backend_name)
            if backend_config.args:
                lines.append(f"[menu.{backend_name}]")
                args_str = ", ".join(f'"{a}"' for a in backend_config.args)
                lines.append(f"args = [{args_str}]")
                lines.append("")

        # Display section (only non-defaults)
        display_lines = []
        if self.display.submenu_prefix != "→ ":
            display_lines.append(f'submenu_prefix = "{self.display.submenu_prefix}"')
        if not self.display.show_info_items:
            display_lines.append("show_info_items = false")
        if not self.display.show_headers:
            display_lines.append("show_headers = false")
        if not self.display.show_separators:
            display_lines.append("show_separators = false")
        if self.display.sort != "alpha":
            display_lines.append(f'sort = "{self.display.sort}"')
        if not self.display.submenus_first:
            display_lines.append("submenus_first = false")

        if display_lines:
            lines.append("[display]")
            lines.extend(display_lines)
            lines.append("")

        # Plugins section
        lines.append("[plugins]")
        repos_str = ", ".join(f'"{r}"' for r in self.plugins.repositories)
        lines.append(f"repositories = [{repos_str}]")
        if self.plugins.allow_unverified:
            lines.append("allow_unverified = true")
        if self.plugins.default_display_mode != "auto":
            lines.append(f'default_display_mode = "{self.plugins.default_display_mode}"')
        if self.plugins.item_threshold != 20:
            lines.append(f"item_threshold = {self.plugins.item_threshold}")

        path.write_text("\n".join(lines) + "\n")
