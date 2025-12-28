"""Fzf menu backend."""

from __future__ import annotations

import subprocess

from menu_kit.core.database import MenuItem
from menu_kit.menu.base import MenuBackend, MenuResult


class FzfBackend(MenuBackend):
    """Menu backend using fzf."""

    @property
    def name(self) -> str:
        return "fzf"

    def is_available(self) -> bool:
        return self._check_command("fzf")

    def show(
        self,
        items: list[MenuItem],
        prompt: str = "",
        extra_args: list[str] | None = None,
    ) -> MenuResult:
        """Display menu using fzf and return selection."""
        # Build the input
        item_map: dict[str, MenuItem] = {}
        lines: list[str] = []

        for item in items:
            display_text = self.format_item(item)
            lines.append(display_text)
            item_map[display_text] = item

        input_text = "\n".join(lines)

        # Build command
        cmd = ["fzf", "--reverse"]
        if prompt:
            cmd.extend(["--prompt", f"{prompt}: "])

        if extra_args:
            cmd.extend(extra_args)

        # Run fzf
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

        # Check if cancelled (fzf returns 130 on escape/ctrl-c)
        if result.returncode != 0:
            return MenuResult(selected=None, cancelled=True)

        selected_text = result.stdout.strip()
        if not selected_text:
            return MenuResult(selected=None, cancelled=True)

        # Find the selected item
        selected_item = item_map.get(selected_text)

        return MenuResult(
            selected=selected_item,
            raw_text=selected_text,
            cancelled=False,
        )
