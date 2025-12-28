# CLAUDE.md

Instructions for Claude Code when working on this project.

## Project Overview

menu-kit is a modular, menu-agnostic launcher for Linux. It's the spiritual successor to dmenu-extended, redesigned with better architecture.

**Key design principles:**
- Everything is a plugin (files, apps, settings are all plugins)
- Menu-agnostic (rofi, fuzzel, dmenu, fzf all supported)
- Composition over inheritance (plugins receive context, don't inherit)
- SQLite for indexing, flat file for display (performance)

## Tech Stack

- Python 3.11+
- TOML for config (built-in `tomllib`)
- SQLite for storage (built-in `sqlite3`)
- No external dependencies for core functionality

## Project Structure

See ARCHITECTURE.md for full details. Key directories:
- `src/menu_kit/core/` - Config, database, plugin context
- `src/menu_kit/menu/` - Menu backend implementations
- `src/menu_kit/plugins/builtin/` - Built-in plugins
- `src/menu_kit/indexing/` - File/app scanning

## Development Commands

```bash
# Install in development mode
pip install -e .

# Run
menu-kit

# Run tests
pytest
```

## Code Style

- Type hints everywhere
- Dataclasses for data structures
- ABC for interfaces
- No global state - pass context through parameters
- **Conventional commits** - use format: `type(scope): description` (e.g., `feat(plugins): add clipboard support`, `fix(cache): handle unicode filenames`)

## Testing Philosophy

Everything should be testable. Design for testability from the start:
- All core logic must have unit tests
- Use dependency injection to make components testable in isolation
- Mock external dependencies (filesystem, subprocesses, menu backends)
- Integration tests for plugin loading and menu interaction
- Test edge cases identified from dmenu-extended issues (see below)

## Lessons from dmenu-extended

Review the [dmenu-extended issues](https://github.com/markhedleyjones/dmenu-extended/issues) and commits to understand historical pain points. Key areas to handle better:

**Unicode/Encoding (#160, #107, #163):**
- Filenames with special characters, surrogates, and non-UTF-8 encoding caused cache build failures
- Always use `errors='surrogateescape'` or similar when handling filesystem paths
- Test with unicode filenames, emoji, and malformed byte sequences

**Performance (#153):**
- Menu showing with noticeable delay was a regression
- Keep startup path minimal - lazy load where possible
- Profile and benchmark menu display latency

**Cache Reliability (#157, #155, #167):**
- Cache builds failed on various edge cases
- Stale entries (deleted files) polluted frequently-used lists
- Design cache invalidation and error recovery from the start

**Open-with Operator (#102, #92):**
- The `:` operator for "open X with Y" had issues with terminal apps and aliases
- Terminal commands need proper PTY handling
- Test the full matrix: GUI apps, terminal apps, aliases, paths with spaces

**Plugin System (#93, #137):**
- Plugin loading and dependency resolution had issues
- Clear error messages when plugins fail to load
- Graceful degradation - one broken plugin shouldn't break everything

## Key Files to Understand

1. `src/menu_kit/core/context.py` - Plugin context API
2. `src/menu_kit/core/runner.py` - Main orchestration
3. `src/menu_kit/menu/base.py` - Menu backend interface
4. `src/menu_kit/plugins/loader.py` - Plugin discovery

## Related Projects

- [dmenu-extended](https://github.com/markhedleyjones/dmenu-extended) - Predecessor, now in maintenance mode
