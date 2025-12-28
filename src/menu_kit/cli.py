"""Command-line interface for menu-kit."""

import argparse
import sys

from menu_kit import __version__


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="menu-kit",
        description="A modular, menu-agnostic launcher for Linux",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-p",
        "--plugin",
        metavar="NAME",
        help="Jump directly to a plugin (e.g., -p network or -p files:recent)",
    )
    parser.add_argument(
        "-b",
        "--backend",
        metavar="NAME",
        help="Override menu backend (rofi, fuzzel, dmenu, fzf)",
    )
    parser.add_argument(
        "--backend-args",
        metavar="ARGS",
        help="Additional arguments to pass to the menu backend",
    )
    parser.add_argument(
        "-t",
        "--terminal",
        action="store_true",
        help="Use fzf for terminal-based selection",
    )
    parser.add_argument(
        "--print",
        dest="print_items",
        action="store_true",
        help="Print items to stdout instead of showing menu",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running it",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild the cache",
    )
    parser.add_argument(
        "selections",
        nargs="*",
        metavar="SELECTION",
        help="Chained selections for scripting (e.g., menu-kit -- 'Files' 'Documents')",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv)

    # TODO: Implement the actual menu logic
    if args.print_items:
        print("Settings")
        print("Plugins")
        return 0

    print(f"menu-kit {__version__}")
    print("Not yet implemented. Use --help for options.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
