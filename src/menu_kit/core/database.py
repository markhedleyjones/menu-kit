"""SQLite database for menu-kit."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from menu_kit.core.config import get_cache_dir


class ItemType(Enum):
    """Type of menu item."""

    ACTION = "action"
    SUBMENU = "submenu"
    INFO = "info"
    SEPARATOR = "separator"
    HEADER = "header"


@dataclass
class MenuItem:
    """A menu item stored in the database."""

    id: str
    title: str
    item_type: ItemType = ItemType.ACTION
    path: str | None = None
    plugin: str | None = None
    metadata: dict[str, Any] | None = None
    icon: str | None = None
    badge: str | None = None

    # Frequency data (populated when querying)
    use_count: int = 0
    last_used: datetime | None = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    item_type TEXT NOT NULL DEFAULT 'action',
    path TEXT,
    plugin TEXT,
    metadata TEXT,
    icon TEXT,
    badge TEXT
);

CREATE TABLE IF NOT EXISTS frequency (
    item_id TEXT PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
    count INTEGER DEFAULT 0,
    last_used TEXT
);

CREATE TABLE IF NOT EXISTS plugin_data (
    plugin TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (plugin, key)
);

CREATE INDEX IF NOT EXISTS idx_items_plugin ON items(plugin);
CREATE INDEX IF NOT EXISTS idx_items_type ON items(item_type);
"""


class Database:
    """SQLite database manager for menu-kit."""

    def __init__(self, path: Path | None = None) -> None:
        """Initialise the database."""
        if path is None:
            cache_dir = get_cache_dir()
            cache_dir.mkdir(parents=True, exist_ok=True)
            path = cache_dir / "index.db"

        self.path = path
        self._connection: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialise the database schema."""
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection."""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add_item(self, item: MenuItem) -> None:
        """Add or update an item in the database."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO items
                (id, title, item_type, path, plugin, metadata, icon, badge)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.title,
                    item.item_type.value,
                    item.path,
                    item.plugin,
                    json.dumps(item.metadata) if item.metadata else None,
                    item.icon,
                    item.badge,
                ),
            )

    def add_items(self, items: list[MenuItem]) -> None:
        """Add or update multiple items in the database."""
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO items
                (id, title, item_type, path, plugin, metadata, icon, badge)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.id,
                        item.title,
                        item.item_type.value,
                        item.path,
                        item.plugin,
                        json.dumps(item.metadata) if item.metadata else None,
                        item.icon,
                        item.badge,
                    )
                    for item in items
                ],
            )

    def get_item(self, item_id: str) -> MenuItem | None:
        """Get a single item by ID."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT i.*, f.count, f.last_used
                FROM items i
                LEFT JOIN frequency f ON i.id = f.item_id
                WHERE i.id = ?
                """,
                (item_id,),
            ).fetchone()

            if row is None:
                return None

            return self._row_to_item(row)

    def get_items(
        self,
        plugin: str | None = None,
        item_type: ItemType | None = None,
        order_by_frequency: bool = False,
    ) -> list[MenuItem]:
        """Get items, optionally filtered."""
        query = """
            SELECT i.*, COALESCE(f.count, 0) as count, f.last_used
            FROM items i
            LEFT JOIN frequency f ON i.id = f.item_id
            WHERE 1=1
        """
        params: list[Any] = []

        if plugin is not None:
            query += " AND i.plugin = ?"
            params.append(plugin)

        if item_type is not None:
            query += " AND i.item_type = ?"
            params.append(item_type.value)

        if order_by_frequency:
            query += " ORDER BY COALESCE(f.count, 0) DESC, i.title ASC"
        else:
            query += " ORDER BY i.title ASC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_item(row) for row in rows]

    def find_item_by_title(self, title: str, prefix: str = "") -> MenuItem | None:
        """Find an item by title, ignoring prefix."""
        # Try exact match first
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT i.*, COALESCE(f.count, 0) as count, f.last_used
                FROM items i
                LEFT JOIN frequency f ON i.id = f.item_id
                WHERE i.title = ? OR i.title = ? OR i.id = ?
                """,
                (title, prefix + title, title),
            ).fetchone()

            if row:
                return self._row_to_item(row)

            # Try case-insensitive
            row = conn.execute(
                """
                SELECT i.*, COALESCE(f.count, 0) as count, f.last_used
                FROM items i
                LEFT JOIN frequency f ON i.id = f.item_id
                WHERE LOWER(i.title) = LOWER(?) OR LOWER(i.title) = LOWER(?)
                """,
                (title, prefix + title),
            ).fetchone()

            if row:
                return self._row_to_item(row)

        return None

    def delete_items_by_plugin(self, plugin: str) -> int:
        """Delete all items for a plugin. Returns count deleted."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM items WHERE plugin = ?", (plugin,))
            return cursor.rowcount

    def record_use(self, item_id: str) -> None:
        """Record that an item was used."""
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO frequency (item_id, count, last_used)
                VALUES (?, 1, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    count = count + 1,
                    last_used = ?
                """,
                (item_id, now, now),
            )

    def get_plugin_data(self, plugin: str, key: str) -> Any | None:
        """Get plugin-specific data."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM plugin_data WHERE plugin = ? AND key = ?",
                (plugin, key),
            ).fetchone()

            if row is None:
                return None

            return json.loads(row["value"]) if row["value"] else None

    def set_plugin_data(self, plugin: str, key: str, value: Any) -> None:
        """Set plugin-specific data."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO plugin_data (plugin, key, value)
                VALUES (?, ?, ?)
                """,
                (plugin, key, json.dumps(value)),
            )

    def delete_plugin_data(self, plugin: str, key: str | None = None) -> None:
        """Delete plugin data. If key is None, delete all data for the plugin."""
        with self._connect() as conn:
            if key is None:
                conn.execute("DELETE FROM plugin_data WHERE plugin = ?", (plugin,))
            else:
                conn.execute(
                    "DELETE FROM plugin_data WHERE plugin = ? AND key = ?",
                    (plugin, key),
                )

    def _row_to_item(self, row: sqlite3.Row) -> MenuItem:
        """Convert a database row to a MenuItem."""
        metadata = json.loads(row["metadata"]) if row["metadata"] else None
        last_used = None
        if row["last_used"]:
            last_used = datetime.fromisoformat(row["last_used"])

        return MenuItem(
            id=row["id"],
            title=row["title"],
            item_type=ItemType(row["item_type"]),
            path=row["path"],
            plugin=row["plugin"],
            metadata=metadata,
            icon=row["icon"],
            badge=row["badge"],
            use_count=row["count"],
            last_used=last_used,
        )
