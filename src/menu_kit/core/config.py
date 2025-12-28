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


@dataclass
class PluginsConfig:
    """Configuration for the plugin system."""

    repositories: list[str] = field(
        default_factory=lambda: ["markhedleyjones/menu-kit-plugins"]
    )
    allow_unverified: bool = False


@dataclass
class Config:
    """Main configuration for menu-kit."""

    menu: MenuConfig = field(default_factory=MenuConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    frequency_tracking: bool = True

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load configuration from file, falling back to defaults."""
        if path is None:
            path = get_config_dir() / "config.toml"

        if not path.exists():
            return cls()

        with path.open("rb") as f:
            data = tomllib.load(f)

        return cls.from_dict(data)

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
        )

        plugins_data = data.get("plugins", {})
        plugins = PluginsConfig(
            repositories=plugins_data.get(
                "repositories", ["markhedleyjones/menu-kit-plugins"]
            ),
            allow_unverified=plugins_data.get("allow_unverified", False),
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
        return backend_config.args
