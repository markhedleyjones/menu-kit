"""Tests for the CLI module."""

from __future__ import annotations

from menu_kit.cli import parse_args


def test_parse_args_defaults() -> None:
    """Test default argument values."""
    args = parse_args([])

    assert args.plugin is None
    assert args.backend is None
    assert args.backend_args is None
    assert args.terminal is False
    assert args.print_items is False
    assert args.dry_run is False
    assert args.rebuild is False
    assert args.selections == []


def test_parse_args_plugin() -> None:
    """Test plugin argument parsing."""
    args = parse_args(["-p", "network"])
    assert args.plugin == "network"

    args = parse_args(["--plugin", "files:recent"])
    assert args.plugin == "files:recent"


def test_parse_args_backend() -> None:
    """Test backend argument parsing."""
    args = parse_args(["-b", "rofi"])
    assert args.backend == "rofi"

    args = parse_args(["--backend", "fzf"])
    assert args.backend == "fzf"


def test_parse_args_terminal() -> None:
    """Test terminal flag."""
    args = parse_args(["-t"])
    assert args.terminal is True

    args = parse_args(["--terminal"])
    assert args.terminal is True


def test_parse_args_print() -> None:
    """Test print flag."""
    args = parse_args(["--print"])
    assert args.print_items is True


def test_parse_args_dry_run() -> None:
    """Test dry-run flag."""
    args = parse_args(["--dry-run"])
    assert args.dry_run is True


def test_parse_args_rebuild() -> None:
    """Test rebuild flag."""
    args = parse_args(["--rebuild"])
    assert args.rebuild is True


def test_parse_args_selections() -> None:
    """Test chained selections."""
    args = parse_args(["--", "Files", "Documents"])
    assert args.selections == ["Files", "Documents"]

    args = parse_args(["Files", "Documents"])
    assert args.selections == ["Files", "Documents"]


def test_parse_args_combined() -> None:
    """Test combining multiple arguments."""
    args = parse_args(
        [
            "-p",
            "network",
            "-b",
            "rofi",
            "--dry-run",
        ]
    )

    assert args.plugin == "network"
    assert args.backend == "rofi"
    assert args.dry_run is True
