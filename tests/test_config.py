"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

from menu_kit.core.config import Config


def test_default_config() -> None:
    """Test that default config has sensible values."""
    config = Config()

    assert config.menu.backend == ""
    assert config.display.submenu_prefix == "→ "
    assert config.frequency_tracking is True
    assert "markhedleyjones/menu-kit-plugins" in config.plugins.repositories


def test_config_from_dict() -> None:
    """Test creating config from dictionary."""
    data = {
        "menu": {
            "backend": "rofi",
            "rofi": {"args": ["-show-icons"]},
        },
        "display": {
            "submenu_prefix": ">> ",
        },
        "frequency_tracking": False,
    }

    config = Config.from_dict(data)

    assert config.menu.backend == "rofi"
    assert config.menu.rofi.args == ["-show-icons"]
    assert config.display.submenu_prefix == ">> "
    assert config.frequency_tracking is False


def test_config_load_missing_file(temp_dir: Path) -> None:
    """Test loading config when file doesn't exist."""
    config = Config.load(temp_dir / "nonexistent.toml")

    # Should return defaults
    assert config.menu.backend == ""
    assert config.frequency_tracking is True


def test_config_load_from_file(temp_dir: Path) -> None:
    """Test loading config from a TOML file."""
    config_path = temp_dir / "config.toml"
    # frequency_tracking must be at root level, before any sections
    config_path.write_text("""
frequency_tracking = false

[menu]
backend = "fuzzel"

[display]
submenu_prefix = "→ "
""")

    config = Config.load(config_path)

    assert config.menu.backend == "fuzzel"
    assert config.frequency_tracking is False


def test_get_backend_args() -> None:
    """Test getting backend-specific arguments."""
    config = Config.from_dict(
        {
            "menu": {
                "rofi": {"args": ["-theme", "dark"]},
                "fzf": {"args": ["--height=50%"]},
            }
        }
    )

    assert config.get_backend_args("rofi") == ["-theme", "dark"]
    assert config.get_backend_args("fzf") == ["--height=50%"]
    assert config.get_backend_args("dmenu") == []
    assert config.get_backend_args("unknown") == []


def test_config_save(temp_dir: Path) -> None:
    """Test saving config to file."""
    config = Config()
    config.frequency_tracking = False
    config.menu.backend = "rofi"

    config_path = temp_dir / "config.toml"
    config.save(config_path)

    # Reload and verify
    loaded = Config.load(config_path)
    assert loaded.frequency_tracking is False
    assert loaded.menu.backend == "rofi"


def test_config_save_roundtrip(temp_dir: Path) -> None:
    """Test that save/load roundtrip preserves values."""
    original = Config.from_dict(
        {
            "menu": {"backend": "fuzzel"},
            "frequency_tracking": False,
            "plugins": {
                "repositories": ["markhedleyjones/menu-kit-plugins", "custom/repo"]
            },
        }
    )

    config_path = temp_dir / "config.toml"
    original.save(config_path)
    loaded = Config.load(config_path)

    assert loaded.menu.backend == original.menu.backend
    assert loaded.frequency_tracking == original.frequency_tracking
    assert loaded.plugins.repositories == original.plugins.repositories


def test_config_save_creates_directory(temp_dir: Path) -> None:
    """Test that save creates parent directories if needed."""
    config = Config()
    config_path = temp_dir / "subdir" / "nested" / "config.toml"

    config.save(config_path)

    assert config_path.exists()
