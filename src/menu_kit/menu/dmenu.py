"""Dmenu menu backend."""

from __future__ import annotations

import subprocess

from menu_kit.core.database import MenuItem
from menu_kit.menu.base import MenuBackend, MenuResult


class DmenuBackend(MenuBackend):
    """Menu backend using dmenu."""

    @property
    def name(self) -> str:
        return "dmenu"

    def is_available(self) -> bool:
        return self._check_command("dmenu")

    def show(
        self,
        items: list[MenuItem],
        prompt: str = "",
        extra_args: list[str] | None = None,
    ) -> MenuResult:
        """Display menu using dmenu and return selection."""
        item_map: dict[str, MenuItem] = {}
        lines: list[str] = []

        for item in items:
            display_text = self.format_item(item)
            lines.append(display_text)
            item_map[display_text] = item

        input_text = "\n".join(lines)

        cmd = ["dmenu", "-i", "-l", "20"]
        if prompt:
            cmd.extend(["-p", prompt])

        if extra_args:
            cmd.extend(extra_args)

        try:
            result = subprocess.run(
                cmd,
                input=input_text,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return MenuResult(selected=None, cancelled=True)

        if result.returncode != 0:
            return MenuResult(selected=None, cancelled=True)

        selected_text = result.stdout.strip()
        if not selected_text:
            return MenuResult(selected=None, cancelled=True)

        # Try exact match first
        selected_item = item_map.get(selected_text)

        # Fallback: dmenu may strip leading whitespace, try matching stripped keys
        if selected_item is None:
            for key, item in item_map.items():
                if key.strip() == selected_text:
                    selected_item = item
                    break

        return MenuResult(
            selected=selected_item,
            raw_text=selected_text,
            cancelled=False,
        )
