"""Stdout menu backend for scripting."""

from __future__ import annotations

import sys

from menu_kit.core.database import MenuItem
from menu_kit.menu.base import MenuBackend, MenuResult


class StdoutBackend(MenuBackend):
    """Menu backend that prints to stdout (for --print mode)."""

    @property
    def name(self) -> str:
        return "stdout"

    def is_available(self) -> bool:
        # Always available
        return True

    def show(
        self,
        items: list[MenuItem],
        prompt: str = "",
        extra_args: list[str] | None = None,
    ) -> MenuResult:
        """Print items to stdout, no selection."""
        for item in items:
            display_text = self.format_item(item)
            print(display_text)

        # stdout mode doesn't do selection
        return MenuResult(selected=None, cancelled=True)

    def print_items(self, items: list[MenuItem]) -> None:
        """Print items to stdout."""
        for item in items:
            display_text = self.format_item(item)
            sys.stdout.write(display_text + "\n")
