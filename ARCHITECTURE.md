# menu-kit Architecture

## Design Decisions

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Plugin API | Composition | Plugins receive context object, no inheritance needed. Cleaner, testable. |
| Config format | TOML | Built into Python 3.11+, human-readable, designed for config files. |
| Storage | SQLite + flat file | SQLite for indexing/queries, flat file generated for fast menu display. |
| Python version | 3.11+ | TOML support, modern type hints, widespread availability. |
| Menu protocol | dmenu stdin/stdout | Universal - works with rofi, fuzzel, dmenu, wofi, bemenu, fzf. |

## Project Structure

```
menu-kit/
├── pyproject.toml
├── src/
│   └── menu_kit/
│       ├── __init__.py
│       ├── cli.py                 # Entry point, argument parsing
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py          # TOML config management
│       │   ├── database.py        # SQLite index + plugin storage
│       │   ├── context.py         # Plugin context object
│       │   └── runner.py          # Main orchestration loop
│       ├── menu/
│       │   ├── __init__.py
│       │   ├── base.py            # Abstract menu interface
│       │   ├── rofi.py
│       │   ├── fuzzel.py
│       │   ├── dmenu.py
│       │   └── fzf.py
│       ├── indexing/
│       │   ├── __init__.py
│       │   ├── scanner.py         # File/folder scanning
│       │   ├── gitignore.py       # .gitignore parser
│       │   └── desktop.py         # .desktop file parser
│       ├── plugins/
│       │   ├── __init__.py
│       │   ├── loader.py          # Plugin discovery/loading
│       │   ├── repository.py      # Remote plugin repos
│       │   └── builtin/
│       │       ├── __init__.py
│       │       ├── files.py
│       │       ├── apps.py
│       │       ├── settings.py
│       │       ├── calculator.py
│       │       └── websearch.py
│       └── executor/
│           ├── __init__.py
│           └── commands.py        # Command execution
└── tests/
```

## Database Schema

```sql
-- Main index (all displayable items)
CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,           -- 'file', 'app', 'plugin', 'action'
    title TEXT NOT NULL,          -- Display text
    path TEXT,                    -- File path or command
    plugin TEXT,                  -- Source plugin name
    metadata TEXT,                -- JSON blob for plugin-specific data
    UNIQUE(type, title, path)
);

-- Usage frequency tracking (optional, can be disabled in config)
CREATE TABLE frequency (
    item_id INTEGER PRIMARY KEY REFERENCES items(id),
    count INTEGER DEFAULT 0,
    last_used TEXT                -- ISO timestamp
);

-- Plugin key-value storage
CREATE TABLE plugin_data (
    plugin TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,                   -- JSON encoded
    PRIMARY KEY (plugin, key)
);

CREATE INDEX idx_items_type ON items(type);
CREATE INDEX idx_items_plugin ON items(plugin);
```

## Plugin Context API

```python
@dataclass
class PluginContext:
    """Passed to plugins - provides all interactions with core."""

    config: Config

    # Menu interaction
    def menu(self, items: list[str], prompt: str = "") -> str | None: ...
    def select(self, items: list[MenuItem], prompt: str = "") -> MenuItem | None: ...
    def notify(self, message: str): ...

    # Storage (backed by SQLite plugin_data table)
    @property
    def storage(self) -> PluginStorage: ...

    # Item registration (for plugins that contribute to main menu)
    def register_items(self, items: list[IndexItem]): ...

    # Execution
    def execute(self, command: str, terminal: bool = False): ...
    def open_file(self, path: Path): ...
    def open_url(self, url: str): ...
```

## Plugin Interface

```python
class Plugin:
    """Base plugin interface."""

    name: str           # Unique identifier (e.g., "files")
    description: str

    def setup(self, ctx: PluginContext) -> None:
        """Called once when plugin is loaded."""
        pass

    def teardown(self, ctx: PluginContext) -> None:
        """Called when plugin is unloaded."""
        pass

    def run(self, ctx: PluginContext, action: str = "") -> None:
        """Called when user selects a plugin item.

        action: Sub-command if invoked via -p plugin:action
        """
        pass

    def index(self, ctx: PluginContext) -> list[MenuItem]:
        """Return items to add to main menu. Called on cache rebuild.

        Plugins can register multiple menu items.
        """
        return []
```

### Multiple Menu Items Per Plugin

A plugin can register multiple top-level items:

```python
class FilesPlugin(Plugin):
    name = "files"

    def index(self, ctx):
        return [
            MenuItem(id="files:browser", title="Files", item_type=ItemType.SUBMENU),
            MenuItem(id="files:recent", title="Recent Files", item_type=ItemType.SUBMENU),
        ]

    def run(self, ctx, action=""):
        if action == "recent":
            self.show_recent(ctx)
        else:
            self.show_browser(ctx)
```

Invoke directly via CLI:
```bash
menu-kit -p files           # Calls run(ctx, action="")
menu-kit -p files:browser   # Calls run(ctx, action="browser")
menu-kit -p files:recent    # Calls run(ctx, action="recent")
```

## Menu Backend Interface

```python
class MenuBackend(ABC):
    """Abstract interface for menu display."""

    @abstractmethod
    def show(self, items: list[str], prompt: str = "") -> str | None:
        """Display menu, return selected item or None if cancelled."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is installed."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""
        pass
```

## Main Runner Flow

```
1. Load config (TOML)
2. Detect/select menu backend
3. Load plugins
4. Generate display file if stale:
   - Query SQLite for all items
   - Sort by frequency
   - Write to ~/.cache/menu-kit/display.txt
5. Pipe display.txt to menu backend
6. Parse selection:
   - Plugin → call plugin.run()
   - File → open with handler
   - App → execute
7. Update frequency in SQLite
8. Regenerate display.txt if needed
```

## File Locations

| Purpose | Path |
|---------|------|
| Config | `~/.config/menu-kit/config.toml` |
| Database | `~/.cache/menu-kit/index.db` |
| Display cache | `~/.cache/menu-kit/display.txt` |
| User plugins | `~/.local/share/menu-kit/plugins/` |
| Plugin data | `~/.local/share/menu-kit/data/<plugin>/` |

## CLI Commands

```bash
# Basic usage
menu-kit                              # Run the menu (auto-detect backend)
menu-kit --backend rofi               # Override backend
menu-kit --backend-args="-show-icons" # One-off backend args (overrides config)

# Direct plugin launch
menu-kit --plugin network       # Jump straight to plugin
menu-kit -p wifi                # Short form

# Terminal modes (no GUI required)
menu-kit --terminal             # Use fzf for interactive selection
menu-kit -t -p apps             # fzf with specific plugin

# Non-interactive / scripting
menu-kit --print                # Print all items to stdout (pipe to head/tail/grep)
menu-kit -p apps --print        # Print plugin items only

# Direct plugin invocation (for keybindings)
menu-kit -p files                 # Run plugin's default action
menu-kit -p files:recent          # Run plugin's sub-action

# Chained selections (for testing/scripting)
menu-kit -- "Files" "Documents"                       # Simulate menu clicks
menu-kit -- "Network" "WiFi" "HomeNetwork" "Connect"  # Multi-step chain
menu-kit --dry-run -- "Network" "WiFi"                # Show what would execute

# Management
menu-kit --rebuild              # Rebuild cache
menu-kit plugin list            # List installed plugins
menu-kit plugin install <name>
menu-kit plugin update
menu-kit config                 # Open config in editor
menu-kit config --init          # Create default config
```

### Backend Selection

| Mode | Backend | Use case |
|------|---------|----------|
| GUI (default) | rofi/fuzzel/dmenu | Desktop launcher |
| `--terminal` | fzf | Terminal-based selection |
| `--print` | stdout | Scripting, piping |

Auto-detection order: rofi → fuzzel → dmenu → fzf → stdout

### Backend Configuration

```toml
# ~/.config/menu-kit/config.toml

[menu]
backend = "rofi"  # Default backend

[menu.rofi]
args = ["-show-icons", "-theme", "mytheme"]

[menu.fuzzel]
args = ["-w", "60", "-l", "20"]

[menu.dmenu]
args = ["-l", "20", "-fn", "monospace:size=12"]

[menu.fzf]
args = ["--height=40%", "--reverse"]
```

Override per-invocation:
```bash
menu-kit --backend-args="-theme othertheme"  # Replaces config args for this run
```

### Custom Pipelines

menu-kit works as both a complete launcher and a data source:

```bash
# Built-in backend (simple)
menu-kit

# Custom pipeline with any menu tool
selection=$(menu-kit --print | rofi -dmenu -p "Launch")
menu-kit -- "$selection"

# With fzf
menu-kit --print | fzf --prompt="Launch: " | xargs -r menu-kit --

# With dmenu
menu-kit --print | dmenu -l 20 | xargs -r menu-kit --
```

This allows using unsupported menu tools or highly customised invocations.

### Direct Invocation vs Chained Selection

Two ways to invoke plugins:

| Method | Syntax | Matches by | Use case |
|--------|--------|------------|----------|
| `-p` | `-p files:recent` | Internal ID | Keybindings, scripts |
| `--` | `-- "Recent Files"` | Display title | Testing, automation |

**`-p plugin` / `-p plugin:action`**
- Uses internal plugin name and action ID
- Robust, doesn't depend on display text
- Recommended for keybindings

**`-- "Selection" "Selection"`**
- Simulates clicking through the menu
- Matches by title, ignoring configured prefixes
- For testing that the menu flow works

### Selection Matching Strategy

When using `-- "Selection"`, matching ignores display prefixes:

```bash
# Config has: submenu_prefix = "→ "
# Menu shows: "→ Files"

menu-kit -- "Files"     # ✓ Matches "→ Files"
menu-kit -- "→ Files"   # ✓ Also works (exact match)
```

Match priority:
1. Exact match on item ID (e.g., `files:browser`)
2. Exact match on title (with or without prefix)
3. Case-insensitive match on title

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (selection made and executed) |
| 1 | Cancelled (user dismissed menu) |
| 2 | Selection not found (in chained mode) |
| 3 | Plugin not found |
| 4 | Execution failed |
| 5 | Config error |
| 6 | No backend available |

## Implementation Phases

### Phase 0: MVP (0.0.1)
Minimal working system to validate architecture and enable CI/publishing.

1. Project scaffolding (pyproject.toml, src layout)
2. CLI entry point with `--plugin`, `--terminal`, `--print`, `--dry-run`
3. Config loading (TOML with defaults)
4. SQLite database (items, frequency, plugin_data tables)
5. Menu backend ABC + rofi + fzf + stdout implementations
6. Plugin ABC with `name`, `run()`, `index()`
7. Plugin loader (builtin + local directory)
8. Bundled plugins:
   - `settings` - configure menu-kit options
   - `plugins` - browse/install plugins from repos
9. Tests with mocked subprocess
10. CI: ruff + mypy + pytest
11. PyPI publishing via GitHub Actions

**Not in MVP:** Display cache file, frequency tracking, plugin verification pipeline.

**Parallel: menu-kit-plugins repo (0.0.1)**
1. Repository structure with index.json
2. `apps` plugin (Name + Exec from .desktop files)
3. CI: auto-generate index.json from manifests

### Phase 1: Performance & Polish
1. Display cache file generation
2. Frequency tracking (optional)
3. Plugin verification pipeline

### Phase 2: Plugin System
1. Plugin loader (discovery, loading)
2. Plugin context implementation
3. Plugin storage API
4. Built-in: apps plugin
5. Built-in: settings plugin

### Phase 3: Indexing
1. File scanner with .gitignore support
2. .desktop file parser
3. Display file generation
4. Frequency tracking

### Phase 4: More Plugins
1. files plugin (browser mode)
2. calculator plugin
3. websearch plugin

### Phase 5: Polish
1. Fuzzel, dmenu, fzf backends
2. Remote plugin repositories
3. Systemd units
4. Documentation

## Planned Plugins

### Content Search
- **content-search** - Full-text search using ripgrep-all (rga)
  - Search PDFs, Office docs, archives, images (OCR), etc.
  - Results show file + matched line
  - Open file at specific line if supported

### Package Management
- **packages** - System package manager abstraction
  - Auto-detect: apt, dnf, pacman, zypper, apk, xbps, nix, brew
  - Search, install, remove, update operations
  - Show installed packages with versions
- **pip** - Python package management
- **cargo** - Rust crate management
- **npm** - Node package management

### Containers
- **containers** - Docker/Podman management
  - List running/stopped containers
  - Start, stop, restart, logs, shell into
  - Image management (list, pull, remove)
  - Volume and network overview

### Projects
- **projects** - Project launcher
  - Scan configured directories for projects (git repos, specific markers)
  - Per-project actions:
    - Open in VS Code / Sublime / editor of choice
    - Open Sublime Merge / git GUI
    - Start Claude Code session
    - Open terminal at project root
    - Custom hooks defined per-project or globally
  - Recent projects sorted by access time

### Profile Switching
- **aws-profiles** - AWS profile/region switcher
  - List profiles from ~/.aws/config
  - Set AWS_PROFILE environment variable
  - Show current active profile
- **git-profiles** - Git identity switcher
  - Switch user.name / user.email
  - Per-directory profile rules

### System
- **system** - Power and session management
  - Logout, restart, shutdown
  - Suspend, hibernate
  - Reload window manager (i3, sway, etc.)
  - Lock screen
- **disk-usage** - Storage overview
  - Show filesystem usage (df)
  - Find large files/directories (ncdu-style)
  - Cleanup suggestions (cache, logs, old kernels)
- **processes** - Process management
  - List running processes (sorted by CPU/memory)
  - Kill/terminate selected process
  - Search by name
  - Show process tree for related processes
- **network** - Network management
  - WiFi: scan, connect, disconnect, saved networks
  - Ethernet: show status, configure
  - VPN: connect/disconnect (NetworkManager, wireguard)
  - Show current IP, gateway, DNS
  - Uses nmcli/networkctl backends
- **bluetooth** - Bluetooth device management
  - Scan for devices
  - Pair/unpair devices
  - Connect/disconnect paired devices
  - Show battery levels where available
  - Uses bluetoothctl backend

### Theming
- **themes** - Theme management plugin
  - Apply themes globally to menu-kit
  - Built-in popular themes:
    - Tokyo Night, Tokyo Night Storm
    - Catppuccin (Latte, Frappé, Macchiato, Mocha)
    - Dracula
    - Gruvbox (Light, Dark)
    - Nord
    - Solarized (Light, Dark)
    - One Dark / One Light
    - Rosé Pine
  - Custom theme definitions in config

## Menu Item Types

Items displayed in menus need semantic types to support:
- Different visual rendering (colours, icons, separators)
- Different interaction behaviour (selectable vs info-only)
- Consistent UX across all menu backends

### Item Categories

```python
class ItemType(Enum):
    ACTION = "action"       # Selectable, executes something
    SUBMENU = "submenu"     # Opens another menu (prefix: "→ " or customisable)
    INFO = "info"           # Display only, not selectable (greyed out)
    SEPARATOR = "separator" # Visual separator line
    HEADER = "header"       # Section header (bold/highlighted, not selectable)
```

### MenuItem Structure

```python
@dataclass
class MenuItem:
    """Rich menu item with type and styling."""

    id: str                          # Unique identifier
    title: str                       # Display text
    item_type: ItemType = ItemType.ACTION

    # Optional styling (theme can override)
    icon: str | None = None          # Nerd font icon or emoji
    badge: str | None = None         # Right-aligned text (e.g., "3 items", "2.1 GB")
    colour: str | None = None        # Hex colour override

    # Metadata for handling
    plugin: str | None = None        # Source plugin
    data: dict | None = None         # Plugin-specific payload
```

### Display Formatting

Each menu backend translates MenuItem to its native format:

**Rofi:**
- INFO items: `<span alpha="50%">text</span>` + non-selectable flag
- SUBMENU items: `→ text` with submenu indicator
- HEADER items: `<b>text</b>` + non-selectable
- Colours via Pango markup

**Fuzzel:**
- Limited styling, use prefix conventions
- INFO: `# text` (comment style)
- SUBMENU: `→ text`

**dmenu:**
- No styling support, prefix-based only
- INFO: `--- text ---`
- SUBMENU: `→ text`

**fzf:**
- ANSI colour codes
- INFO: dimmed text
- Headers via --header flag

### Configuration

```toml
[display]
# Prefix conventions (customisable)
submenu_prefix = "→ "
info_prefix = ""
header_prefix = ""
separator = "─────────────────────"

# Whether to show non-selectable items
show_info_items = true
show_headers = true
show_separators = true
```

## Theming System

Themes define colours for menu item types and states.

### Theme Structure

```toml
[theme]
name = "Tokyo Night"

[theme.colours]
background = "#1a1b26"
foreground = "#c0caf5"
selection_bg = "#33467c"
selection_fg = "#c0caf5"
border = "#29a4bd"

# Item type colours
action = "#c0caf5"
submenu = "#7aa2f7"
info = "#565f89"
header = "#bb9af7"
separator = "#3b4261"

# Semantic colours
success = "#9ece6a"
warning = "#e0af68"
error = "#f7768e"
accent = "#7dcfff"
```

### Built-in Themes

Themes plugin provides presets that can be selected:
- Auto-detect from terminal/system theme where possible
- Manual selection via menu or config
- Export current colours to theme file

### Per-Backend Overrides

Some backends have specific options:

```toml
[menu.rofi]
theme_file = ""  # Use menu-kit theme conversion
# OR
theme_file = "~/.config/rofi/themes/custom.rasi"  # Use external rofi theme

[menu.fuzzel]
# Fuzzel has limited theming, map to available options
```

## Plugin System

### Versioning

Two version numbers:
- **menu-kit version** - release version (semver)
- **Plugin API version** - separate, increments only when plugin interface breaks

Plugins declare compatibility:
```toml
[plugin]
name = "network"
version = "1.2.0"
api_version = "1"
min_menu_kit = "0.5.0"  # Optional
```

### Plugin Formats

Support both formats (auto-detected):

**Single file** - `plugin_name.py`
- Simple plugins, easy to share
- Metadata in module docstring or decorators

**Package directory** - `plugin_name/`
```
network/
├── manifest.toml
├── __init__.py
├── wifi.py
├── vpn.py
└── assets/
    └── icons/
```

### Dependencies

```toml
[plugin.dependencies]
# Python packages (pip)
python = ["requests>=2.28", "beautifulsoup4"]

# System packages (check/warn only, never auto-install)
system.apt = ["ripgrep", "bluez"]
system.dnf = ["ripgrep", "bluez"]
system.pacman = ["ripgrep", "bluez"]

# Other plugins
plugins = ["core-utils>=1.0"]

# Plugin works without these but with reduced features
[plugin.optional_dependencies]
python = ["pillow"]

# Plugins that conflict (can't both be active)
[plugin.conflicts]
plugins = ["network-lite"]
```

System dependencies:
- menu-kit checks if installed, warns if missing
- Shows install command for user's package manager
- Marks plugin as "degraded" if deps missing
- **Never auto-installs** (security)

### Storage Locations

| Location | Purpose | Priority |
|----------|---------|----------|
| `src/menu_kit/plugins/builtin/` | Bundled with menu-kit | 1 (lowest) |
| `/usr/share/menu-kit/plugins/` | System-wide (distro packages) | 2 |
| `~/.local/share/menu-kit/plugins/` | User-installed from repos | 3 |
| `~/.config/menu-kit/plugins/` | Local/private plugins | 4 (highest) |

Later overrides earlier if same plugin name.

### Bundled vs Optional Plugins

**Bundled** (in menu-kit core):
- `settings` - configure menu-kit
- `plugins` - browse, install, manage plugins

**Optional** (in `markhedleyjones/menu-kit-plugins` repo):
- `apps` - .desktop application launcher
- `files` - file browser
- `network` - WiFi/ethernet/VPN via NetworkManager
- `bluetooth` - device management via bluez
- `containers` - docker/podman management
- `packages` - system package manager
- `projects` - project launcher
- `processes` - process management
- `disk-usage` - storage overview
- `system` - power/session management
- `profiles` - AWS/git profile switching
- `content-search` - ripgrep-all search
- `themes` - theme management

First run shows only Settings and Plugins. User installs what they need.

### Plugin Verification

Plugins have a verification status:

| Status | Meaning |
|--------|---------|
| ✓ Verified | Passed automated security scan |
| ⚠ Unverified | From third-party repo, not scanned |
| 🔒 Official | Maintained by menu-kit team |
| ❌ Flagged | Known security issue |

Automated verification pipeline:
- Static analysis (bandit, semgrep)
- Dependency audit (known vulnerabilities)
- AI-assisted code review for suspicious patterns
- Sandboxed execution tests
- Human review for official status

### Repository System

Official plugins hosted on GitHub at `markhedleyjones/menu-kit-plugins`.

```toml
# ~/.config/menu-kit/config.toml
[plugins]
repositories = [
    "markhedleyjones/menu-kit-plugins",   # Official (default, always included)
    "someuser/their-plugins",             # Third-party
    "file:///home/user/my-plugins",       # Private/local
]

# Trust settings
allow_unverified = false  # Block unverified plugins by default
```

Short-form `user/repo` expands to `https://raw.githubusercontent.com/user/repo/main/index.json`.

Repository index format:
```json
{
    "version": 1,
    "plugins": {
        "network": {
            "version": "1.2.0",
            "api_version": "1",
            "description": "Network management via NetworkManager",
            "author": "menu-kit team",
            "license": "MIT",
            "download_url": "https://github.com/.../network-1.2.0.tar.gz",
            "checksum": "sha256:abcd1234...",
            "verified": true,
            "verified_at": "2025-01-15T10:30:00Z",
            "dependencies": {
                "python": ["requests>=2.28"],
                "system": {"apt": ["network-manager"]}
            },
            "conflicts": []
        }
    }
}
```

### Plugin Discovery UI

Built-in `plugins` plugin for in-menu management:

```
→ Plugins
  ├── Installed (12)
  │   ├── network v1.2.0 ✓
  │   ├── bluetooth v1.0.0 ⚠ missing: bluez
  │   └── containers v2.1.0 🔒
  ├── Updates Available (2)
  │   ├── network 1.2.0 → 1.3.0
  │   └── themes 1.0.0 → 1.1.0
  ├── Browse
  │   ├── By Category
  │   ├── Popular
  │   ├── Recently Updated
  │   └── Search...
  ├── Repositories
  │   ├── Official (menu-kit.dev) ✓
  │   ├── user/extras ⚠
  │   └── Add Repository...
  └── Settings
      ├── Allow Unverified: No
      └── Auto-update: Check Weekly
```

### Local/Private Plugins

Two mechanisms:

1. **Local directory** - `~/.config/menu-kit/plugins/`
   - Not from any repo, loaded directly
   - For personal hacks, experiments, work-specific tools
   - Always loaded, no verification (user's own code)

2. **Private repositories**
   - Self-hosted index.json
   - Useful for teams/companies sharing internal plugins
   - Can use file:// URLs for fully offline repos

## Lessons from dmenu-extended

**Keep:**
- Single responsibility for menu interface
- XDG standards compliance
- Preference defaults with clear documentation
- Backwards compatibility migrations

**Avoid:**
- Monolithic class with 40+ methods
- Global state
- String-based code execution for plugins
- Tight coupling to specific menu backend
- Mixed concerns in cache building
