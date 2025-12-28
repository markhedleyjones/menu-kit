# menu-kit

A modular, menu-agnostic launcher for Linux with plugin-first architecture.

## Overview

menu-kit is a launcher/menu system that works with multiple menu backends (rofi, fuzzel, dmenu, fzf) while providing a unified plugin system. Everything is a plugin - file browsing, app launching, settings, search.

**Status:** Early development - architecture defined, implementation starting.

## Features (Planned)

- **Menu-agnostic** - Works with rofi, fuzzel, dmenu, wofi, bemenu, fzf
- **Plugin-first** - Core features implemented as plugins
- **Smart indexing** - .gitignore aware file scanning
- **SQLite backend** - Fast queries, frequency tracking, incremental updates
- **TOML config** - Human-readable configuration
- **Systemd integration** - Background index rebuilding

## Architecture

```
┌─────────────────────────────────────┐
│         Core (Python 3.11+)         │
│  - Config (TOML)                    │
│  - Database (SQLite)                │
│  - Plugin loader                    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Menu Abstraction Layer         │
│   (stdin/stdout dmenu protocol)     │
└──────────────┬──────────────────────┘
               │
     ┌─────────┼─────────┐
     ▼         ▼         ▼
   rofi     fuzzel     dmenu
```

## Built-in Plugins

| Plugin | Description |
|--------|-------------|
| `apps` | Application launcher (.desktop files) |
| `files` | File browser with contextual navigation |
| `settings` | In-menu configuration |
| `calculator` | Evaluate expressions |
| `websearch` | Configurable search engines |

## Requirements

- Python 3.11+
- One of: rofi, fuzzel, dmenu, fzf

## Configuration

Config lives at `~/.config/menu-kit/config.toml`:

```toml
[menu]
backend = "auto"  # auto-detect, or: rofi, fuzzel, dmenu, fzf
prompt = ">"
lines = 15

[indexing]
watch_folders = ["~/"]
ignore_patterns = [".git", "node_modules", "__pycache__"]
respect_gitignore = true

[plugins]
enabled = ["files", "apps", "settings", "calculator"]
```

## Background

menu-kit is the spiritual successor to [dmenu-extended](https://github.com/markhedleyjones/dmenu-extended), redesigned with:
- Menu-agnostic architecture (not tied to dmenu)
- Plugin-first design (everything is a plugin)
- Modern Python practices (type hints, dataclasses, SQLite)
- Better separation of concerns

## Licence

MIT
