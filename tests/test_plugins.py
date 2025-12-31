"""Tests for the plugin system."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from menu_kit.core.config import Config
from menu_kit.core.database import Database, ItemType, MenuItem
from menu_kit.menu.base import MenuResult
from menu_kit.plugins.base import MenuCancelled, PluginContext


def test_plugin_context_menu_with_back_button(config: Config, database: Database) -> None:
    """Test that back button is added when show_back=True."""
    mock_backend = MagicMock()
    mock_backend.show.return_value = MenuResult(cancelled=True, selected=None)

    ctx = PluginContext(config=config, database=database, menu_backend=mock_backend)

    items = [
        MenuItem(id="item1", title="Item 1"),
        MenuItem(id="item2", title="Item 2"),
    ]

    with pytest.raises(MenuCancelled):
        ctx.menu(items, prompt="Test", show_back=True)

    # Check that show was called with back button appended
    call_args = mock_backend.show.call_args
    display_items = call_args[0][0]

    assert len(display_items) == 3
    assert display_items[0].id == "item1"
    assert display_items[1].id == "item2"
    assert display_items[2].id == "_back"
    assert display_items[2].title == "Back"


def test_plugin_context_menu_without_back_button(config: Config, database: Database) -> None:
    """Test that back button is not added when show_back=False."""
    mock_backend = MagicMock()
    mock_backend.show.return_value = MenuResult(cancelled=True, selected=None)

    ctx = PluginContext(config=config, database=database, menu_backend=mock_backend)

    items = [
        MenuItem(id="item1", title="Item 1"),
        MenuItem(id="item2", title="Item 2"),
    ]

    with pytest.raises(MenuCancelled):
        ctx.menu(items, prompt="Test", show_back=False)

    call_args = mock_backend.show.call_args
    display_items = call_args[0][0]

    assert len(display_items) == 2
    assert display_items[0].id == "item1"
    assert display_items[1].id == "item2"


def test_plugin_context_menu_back_returns_none(config: Config, database: Database) -> None:
    """Test that selecting back button returns None."""
    mock_backend = MagicMock()
    back_item = MenuItem(id="_back", title="Back", item_type=ItemType.ACTION)
    mock_backend.show.return_value = MenuResult(cancelled=False, selected=back_item)

    ctx = PluginContext(config=config, database=database, menu_backend=mock_backend)

    items = [MenuItem(id="item1", title="Item 1")]

    result = ctx.menu(items, prompt="Test", show_back=True)

    assert result is None


def test_plugin_context_menu_selection(config: Config, database: Database) -> None:
    """Test that selecting an item returns it."""
    mock_backend = MagicMock()
    selected_item = MenuItem(id="item1", title="Item 1")
    mock_backend.show.return_value = MenuResult(cancelled=False, selected=selected_item)

    ctx = PluginContext(config=config, database=database, menu_backend=mock_backend)

    items = [selected_item, MenuItem(id="item2", title="Item 2")]

    result = ctx.menu(items, prompt="Test", show_back=True)

    assert result is not None
    assert result.id == "item1"


def test_plugin_context_menu_cancelled_raises_exception(config: Config, database: Database) -> None:
    """Test that cancelling (ESC) raises MenuCancelled exception."""
    mock_backend = MagicMock()
    mock_backend.show.return_value = MenuResult(cancelled=True, selected=None)

    ctx = PluginContext(config=config, database=database, menu_backend=mock_backend)

    items = [MenuItem(id="item1", title="Item 1")]

    with pytest.raises(MenuCancelled):
        ctx.menu(items, prompt="Test", show_back=True)
