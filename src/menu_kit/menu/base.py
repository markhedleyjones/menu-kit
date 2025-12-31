"""Abstract base class for menu backends."""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass

from menu_kit.core.database import ItemType, MenuItem


@dataclass
class MenuResult:
    """Result from a menu selection."""

    selected: MenuItem | None
    raw_text: str | None = None
    cancelled: bool = False


class MenuBackend(ABC):
    """Abstract interface for menu display."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is installed."""
        ...

    @abstractmethod
    def show(
        self,
        items: list[MenuItem],
        prompt: str = "",
        extra_args: list[str] | None = None,
    ) -> MenuResult:
        """Display menu and return the selection."""
        ...

    def format_item(self, item: MenuItem) -> str:
        """Format a menu item for display with consistent gutter."""
        # Gutter icons (2 chars wide for alignment)
        if item.item_type == ItemType.SUBMENU:
            gutter = "→ "
        elif item.id == "_back":
            gutter = "← "
        else:
            gutter = "  "

        text = f"{gutter}{item.title}"

        if item.badge:
            text = f"{text}  ({item.badge})"

        return text

    def _check_command(self, cmd: str) -> bool:
        """Check if a command is available."""
        return shutil.which(cmd) is not None


def get_available_backends() -> list[type[MenuBackend]]:
    """Get all available menu backend classes."""
    from menu_kit.menu.dmenu import DmenuBackend
    from menu_kit.menu.fuzzel import FuzzelBackend
    from menu_kit.menu.fzf import FzfBackend
    from menu_kit.menu.rofi import RofiBackend
    from menu_kit.menu.stdout import StdoutBackend

    return [RofiBackend, DmenuBackend, FuzzelBackend, FzfBackend, StdoutBackend]


# GUI backends that open a window (work with keyboard shortcuts)
GUI_BACKENDS = ["rofi", "dmenu", "fuzzel"]

# Terminal backends that need a terminal (fzf) or just print (stdout)
TERMINAL_BACKENDS = ["fzf", "stdout"]


def get_backend(name: str | None = None) -> MenuBackend | None:
    """Get a menu backend by name, or auto-detect."""
    from menu_kit.menu.dmenu import DmenuBackend
    from menu_kit.menu.fuzzel import FuzzelBackend
    from menu_kit.menu.fzf import FzfBackend
    from menu_kit.menu.rofi import RofiBackend
    from menu_kit.menu.stdout import StdoutBackend

    backends: dict[str, type[MenuBackend]] = {
        "rofi": RofiBackend,
        "dmenu": DmenuBackend,
        "fuzzel": FuzzelBackend,
        "fzf": FzfBackend,
        "stdout": StdoutBackend,
    }

    if name:
        backend_class = backends.get(name)
        if backend_class:
            backend = backend_class()
            if backend.is_available():
                return backend
        return None

    # Auto-detect priority: rofi → dmenu → fuzzel → fzf → stdout
    priority = [RofiBackend, DmenuBackend, FuzzelBackend, FzfBackend, StdoutBackend]
    for backend_class in priority:
        backend = backend_class()
        if backend.is_available():
            return backend

    return None


def check_gui_backend_available() -> bool:
    """Check if any GUI backend is available."""
    from menu_kit.menu.dmenu import DmenuBackend
    from menu_kit.menu.fuzzel import FuzzelBackend
    from menu_kit.menu.rofi import RofiBackend

    backends: list[type[MenuBackend]] = [RofiBackend, DmenuBackend, FuzzelBackend]
    return any(backend_class().is_available() for backend_class in backends)
