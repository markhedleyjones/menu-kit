# Current Task: Plugin Repository System

## Status: COMPLETE

All plugin repository functionality is working end-to-end.

## Completed Steps
1. [x] Commit and push menu-kit-plugins (apps fix, files plugin, index.json)
2. [x] Wait for CI to run and verify index.json is on GitHub
3. [x] Test browse flow in menu-kit (fetch index from GitHub)
4. [x] Test install flow (download plugin from GitHub)
5. [x] Test uninstall flow
6. [x] Fix test failures (tests now handle both network/no-network cases)
7. [x] Fix loader to clear ALL items on rebuild (not just loaded plugins)
8. [x] Commit all changes to menu-kit

## What Works
- Browse: Fetches index.json from GitHub, shows available plugins
- Install: Downloads plugin __init__.py from GitHub raw URL
- Uninstall: Removes plugin directory and clears database items
- Rebuild: Properly clears stale items from uninstalled plugins
- Tests: All 106 tests pass (17 new for plugin repository flow)

## Commits Made
- menu-kit-plugins: `feat: add files plugin and fix apps ID lookup`
- menu-kit: `feat(plugins): add browse, install, and uninstall from GitHub repos`
- menu-kit: `fix(loader): clear all items on rebuild to remove stale plugin data`
- menu-kit: `test(plugins): add comprehensive tests for browse/install/uninstall flow`

## Key Files
- menu-kit: `src/menu_kit/plugins/builtin/plugins.py` - browse/install/uninstall logic
- menu-kit: `src/menu_kit/plugins/loader.py` - index rebuild with full clear
- menu-kit: `tests/test_plugin_repository.py` - comprehensive tests for plugin flow
- menu-kit-plugins: `.github/workflows/build-index.yml` - CI to generate index.json

## Testing
```bash
menu-kit --print  # Shows installed plugins' items
menu-kit -p plugins:browse  # Direct to browse menu
menu-kit --rebuild  # Rebuild index (clears stale items)
```
