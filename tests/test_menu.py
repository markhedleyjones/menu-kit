"""Tests for menu backend selection and Wayland detection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from menu_kit.menu.base import get_backend, is_wayland


class TestWaylandDetection:
    """Tests for Wayland environment detection."""

    def test_wayland_detection_via_session_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Detect Wayland via XDG_SESSION_TYPE environment variable."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert is_wayland() is True

    def test_wayland_detection_via_session_type_uppercase(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Detect Wayland via XDG_SESSION_TYPE (case insensitive)."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "WAYLAND")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert is_wayland() is True

    def test_wayland_detection_via_display(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Detect Wayland via WAYLAND_DISPLAY environment variable."""
        monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        assert is_wayland() is True

    def test_wayland_detection_both_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Detect Wayland when both environment variables are set."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        assert is_wayland() is True

    def test_x11_detection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Detect X11 (not Wayland) when session type is x11."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert is_wayland() is False

    def test_no_display_server_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default to not Wayland when no environment variables are set."""
        monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert is_wayland() is False


class TestBackendPriority:
    """Tests for backend selection priority based on display server."""

    def test_wayland_priority_fuzzel_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Wayland, fuzzel should be tried before rofi."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")

        # Mock all backends as unavailable except fuzzel
        with (
            patch("menu_kit.menu.fuzzel.FuzzelBackend") as mock_fuzzel,
            patch("menu_kit.menu.rofi.RofiBackend") as mock_rofi,
            patch("menu_kit.menu.dmenu.DmenuBackend") as mock_dmenu,
            patch("menu_kit.menu.fzf.FzfBackend") as mock_fzf,
            patch("menu_kit.menu.stdout.StdoutBackend") as mock_stdout,
        ):
            # Only fuzzel is available
            fuzzel_instance = MagicMock()
            fuzzel_instance.is_available.return_value = True
            mock_fuzzel.return_value = fuzzel_instance

            for mock in [mock_rofi, mock_dmenu, mock_fzf]:
                instance = MagicMock()
                instance.is_available.return_value = False
                mock.return_value = instance

            stdout_instance = MagicMock()
            stdout_instance.is_available.return_value = True
            mock_stdout.return_value = stdout_instance

            backend = get_backend()

            # Should get fuzzel (not stdout, even though stdout is available)
            assert backend == fuzzel_instance
            # Verify fuzzel was tried first
            mock_fuzzel.assert_called()

    def test_wayland_priority_fallback_to_rofi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Wayland, if fuzzel unavailable, fall back to rofi."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")

        with (
            patch("menu_kit.menu.fuzzel.FuzzelBackend") as mock_fuzzel,
            patch("menu_kit.menu.rofi.RofiBackend") as mock_rofi,
            patch("menu_kit.menu.dmenu.DmenuBackend") as mock_dmenu,
            patch("menu_kit.menu.fzf.FzfBackend") as mock_fzf,
            patch("menu_kit.menu.stdout.StdoutBackend") as mock_stdout,
        ):
            # Fuzzel not available, rofi available
            fuzzel_instance = MagicMock()
            fuzzel_instance.is_available.return_value = False
            mock_fuzzel.return_value = fuzzel_instance

            rofi_instance = MagicMock()
            rofi_instance.is_available.return_value = True
            mock_rofi.return_value = rofi_instance

            for mock in [mock_dmenu, mock_fzf]:
                instance = MagicMock()
                instance.is_available.return_value = False
                mock.return_value = instance

            stdout_instance = MagicMock()
            stdout_instance.is_available.return_value = True
            mock_stdout.return_value = stdout_instance

            backend = get_backend()

            # Should get rofi (fuzzel was tried first but unavailable)
            assert backend == rofi_instance

    def test_x11_priority_rofi_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On X11, rofi should be tried before fuzzel."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")

        with (
            patch("menu_kit.menu.rofi.RofiBackend") as mock_rofi,
            patch("menu_kit.menu.dmenu.DmenuBackend") as mock_dmenu,
            patch("menu_kit.menu.fuzzel.FuzzelBackend") as mock_fuzzel,
            patch("menu_kit.menu.fzf.FzfBackend") as mock_fzf,
            patch("menu_kit.menu.stdout.StdoutBackend") as mock_stdout,
        ):
            # Only rofi is available
            rofi_instance = MagicMock()
            rofi_instance.is_available.return_value = True
            mock_rofi.return_value = rofi_instance

            for mock in [mock_dmenu, mock_fuzzel, mock_fzf]:
                instance = MagicMock()
                instance.is_available.return_value = False
                mock.return_value = instance

            stdout_instance = MagicMock()
            stdout_instance.is_available.return_value = True
            mock_stdout.return_value = stdout_instance

            backend = get_backend()

            # Should get rofi (not stdout)
            assert backend == rofi_instance
            # Verify rofi was tried first
            mock_rofi.assert_called()

    def test_explicit_backend_respected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit backend choice is respected regardless of display server."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")

        with (
            patch("menu_kit.menu.rofi.RofiBackend") as mock_rofi,
            patch("menu_kit.menu.fuzzel.FuzzelBackend") as mock_fuzzel,
        ):
            rofi_instance = MagicMock()
            rofi_instance.is_available.return_value = True
            mock_rofi.return_value = rofi_instance

            fuzzel_instance = MagicMock()
            fuzzel_instance.is_available.return_value = True
            mock_fuzzel.return_value = fuzzel_instance

            # Explicitly request rofi on Wayland
            backend = get_backend("rofi")

            # Should get rofi even though we're on Wayland (fuzzel would be auto-selected)
            assert backend == rofi_instance

    def test_fallback_to_stdout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls back to stdout when no GUI backends are available."""
        monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)

        with (
            patch("menu_kit.menu.rofi.RofiBackend") as mock_rofi,
            patch("menu_kit.menu.dmenu.DmenuBackend") as mock_dmenu,
            patch("menu_kit.menu.fuzzel.FuzzelBackend") as mock_fuzzel,
            patch("menu_kit.menu.fzf.FzfBackend") as mock_fzf,
            patch("menu_kit.menu.stdout.StdoutBackend") as mock_stdout,
        ):
            # All GUI backends unavailable
            for mock in [mock_rofi, mock_dmenu, mock_fuzzel, mock_fzf]:
                instance = MagicMock()
                instance.is_available.return_value = False
                mock.return_value = instance

            stdout_instance = MagicMock()
            stdout_instance.is_available.return_value = True
            mock_stdout.return_value = stdout_instance

            backend = get_backend()

            # Should fall back to stdout
            assert backend == stdout_instance
