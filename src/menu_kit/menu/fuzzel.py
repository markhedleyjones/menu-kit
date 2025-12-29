"""Fuzzel menu backend."""

from __future__ import annotations

import subprocess

from menu_kit.core.database import MenuItem
from menu_kit.menu.base import MenuBackend, MenuResult


class FuzzelBackend(MenuBackend):
    """Menu backend using fuzzel."""

    @property
    def name(self) -> str:
        return "fuzzel"

    def is_available(self) -> bool:
        return self._check_command("fuzzel")

    def show(
        self,
        items: list[MenuItem],
        prompt: str = "",
        extra_args: list[str] | None = None,
    ) -> MenuResult:
        """Display menu using fuzzel and return selection."""
        lines: list[str] = []

        for item in items:
            display_text = self.format_item(item)
            lines.append(display_text)

        input_text = "\n".join(lines)

        # Use --index to return line number instead of text
        cmd = ["fuzzel", "--dmenu", "--index"]
        if prompt:
            cmd.extend(["--prompt", f"{prompt}: "])

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

        index_str = result.stdout.strip()
        if not index_str:
            return MenuResult(selected=None, cancelled=True)

        # Look up by index
        try:
            index = int(index_str)
            selected_item = items[index]
        except (ValueError, IndexError):
            return MenuResult(selected=None, cancelled=True)

        return MenuResult(
            selected=selected_item,
            raw_text=lines[index] if index < len(lines) else None,
            cancelled=False,
        )
