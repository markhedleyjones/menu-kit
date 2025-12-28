"""Tests for the database module."""

from __future__ import annotations

from menu_kit.core.database import Database, ItemType, MenuItem


def test_add_and_get_item(database: Database) -> None:
    """Test adding and retrieving an item."""
    item = MenuItem(
        id="test:item",
        title="Test Item",
        item_type=ItemType.ACTION,
        plugin="test",
    )

    database.add_item(item)
    retrieved = database.get_item("test:item")

    assert retrieved is not None
    assert retrieved.id == "test:item"
    assert retrieved.title == "Test Item"
    assert retrieved.item_type == ItemType.ACTION
    assert retrieved.plugin == "test"


def test_add_multiple_items(database: Database) -> None:
    """Test adding multiple items at once."""
    items = [
        MenuItem(id="item1", title="Item 1", plugin="test"),
        MenuItem(id="item2", title="Item 2", plugin="test"),
        MenuItem(id="item3", title="Item 3", plugin="test"),
    ]

    database.add_items(items)

    assert database.get_item("item1") is not None
    assert database.get_item("item2") is not None
    assert database.get_item("item3") is not None


def test_get_items_filtered_by_plugin(database: Database) -> None:
    """Test filtering items by plugin."""
    items = [
        MenuItem(id="a:1", title="A1", plugin="plugin_a"),
        MenuItem(id="a:2", title="A2", plugin="plugin_a"),
        MenuItem(id="b:1", title="B1", plugin="plugin_b"),
    ]
    database.add_items(items)

    plugin_a_items = database.get_items(plugin="plugin_a")

    assert len(plugin_a_items) == 2
    assert all(item.plugin == "plugin_a" for item in plugin_a_items)


def test_get_items_filtered_by_type(database: Database) -> None:
    """Test filtering items by type."""
    items = [
        MenuItem(id="action", title="Action", item_type=ItemType.ACTION),
        MenuItem(id="submenu", title="Submenu", item_type=ItemType.SUBMENU),
        MenuItem(id="info", title="Info", item_type=ItemType.INFO),
    ]
    database.add_items(items)

    submenus = database.get_items(item_type=ItemType.SUBMENU)

    assert len(submenus) == 1
    assert submenus[0].id == "submenu"


def test_find_item_by_title(database: Database) -> None:
    """Test finding item by title."""
    item = MenuItem(id="files", title="Files", item_type=ItemType.SUBMENU)
    database.add_item(item)

    # Exact match
    found = database.find_item_by_title("Files")
    assert found is not None
    assert found.id == "files"

    # With prefix
    found = database.find_item_by_title("Files", prefix="→ ")
    assert found is not None

    # Case insensitive
    found = database.find_item_by_title("files")
    assert found is not None


def test_find_item_by_id(database: Database) -> None:
    """Test finding item by ID via title search."""
    item = MenuItem(id="settings:theme", title="Theme", plugin="settings")
    database.add_item(item)

    # Search by ID should also work
    found = database.find_item_by_title("settings:theme")
    assert found is not None
    assert found.id == "settings:theme"


def test_delete_items_by_plugin(database: Database) -> None:
    """Test deleting all items for a plugin."""
    items = [
        MenuItem(id="a:1", title="A1", plugin="plugin_a"),
        MenuItem(id="a:2", title="A2", plugin="plugin_a"),
        MenuItem(id="b:1", title="B1", plugin="plugin_b"),
    ]
    database.add_items(items)

    deleted = database.delete_items_by_plugin("plugin_a")

    assert deleted == 2
    assert database.get_item("a:1") is None
    assert database.get_item("b:1") is not None


def test_frequency_tracking(database: Database) -> None:
    """Test recording and retrieving usage frequency."""
    item = MenuItem(id="test", title="Test")
    database.add_item(item)

    # Initial count should be 0
    retrieved = database.get_item("test")
    assert retrieved is not None
    assert retrieved.use_count == 0

    # Record uses
    database.record_use("test")
    database.record_use("test")
    database.record_use("test")

    retrieved = database.get_item("test")
    assert retrieved is not None
    assert retrieved.use_count == 3
    assert retrieved.last_used is not None


def test_get_items_ordered_by_frequency(database: Database) -> None:
    """Test ordering items by usage frequency."""
    items = [
        MenuItem(id="rare", title="Rare"),
        MenuItem(id="common", title="Common"),
        MenuItem(id="never", title="Never"),
    ]
    database.add_items(items)

    # Use 'common' more than 'rare'
    database.record_use("common")
    database.record_use("common")
    database.record_use("common")
    database.record_use("rare")

    ordered = database.get_items(order_by_frequency=True)

    assert ordered[0].id == "common"
    assert ordered[1].id == "rare"


def test_plugin_data_storage(database: Database) -> None:
    """Test storing and retrieving plugin data."""
    # Store some data
    database.set_plugin_data("test_plugin", "key1", {"value": 123})
    database.set_plugin_data("test_plugin", "key2", ["a", "b", "c"])

    # Retrieve it
    assert database.get_plugin_data("test_plugin", "key1") == {"value": 123}
    assert database.get_plugin_data("test_plugin", "key2") == ["a", "b", "c"]
    assert database.get_plugin_data("test_plugin", "nonexistent") is None


def test_plugin_data_delete(database: Database) -> None:
    """Test deleting plugin data."""
    database.set_plugin_data("test", "key1", "value1")
    database.set_plugin_data("test", "key2", "value2")

    # Delete single key
    database.delete_plugin_data("test", "key1")
    assert database.get_plugin_data("test", "key1") is None
    assert database.get_plugin_data("test", "key2") == "value2"

    # Delete all keys
    database.delete_plugin_data("test")
    assert database.get_plugin_data("test", "key2") is None


def test_item_metadata(database: Database) -> None:
    """Test storing and retrieving item metadata."""
    item = MenuItem(
        id="test",
        title="Test",
        metadata={"custom": "data", "count": 42},
    )
    database.add_item(item)

    retrieved = database.get_item("test")
    assert retrieved is not None
    assert retrieved.metadata == {"custom": "data", "count": 42}
