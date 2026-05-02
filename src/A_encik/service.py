"""Service layer for A-encik using CRUDService."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from A.core.service import CRUDService

from A_encik.data.storage import get_db, row_to_dict

_encik_service: EncikService | None = None


class EncikService(CRUDService):
    """Extended CRUDService for encik with JSON columns and FTS5.
    
    Features:
    - JSON serialization for complex columns
    - FTS5 full-text search indexing
    - Title and UUID prefix lookups
    - Custom search methods
    """

    def __init__(self, db):
        """Initialize EncikService."""
        super().__init__(db, "encik")

    # JSON columns that need serialization
    _JSON_LIST_FIELDS: tuple[str, ...] = (
        "superklaso", "ligilo", "fonto", "citajo", "semantika"
    )
    _JSON_DICT_FIELDS: tuple[str, ...] = (
        "terminologio", "difinoj", "datumo"
    )

    def _serialize(self, data: dict[str, Any]) -> dict[str, Any]:
        """JSON-serialize complex fields before DB insert."""
        result = dict(data)
        # Serialize list-type fields
        for field in self._JSON_LIST_FIELDS:
            if field in result and isinstance(result[field], (list, dict)):
                result[field] = json.dumps(result[field], ensure_ascii=False)
        # Serialize dict-type fields
        for field in self._JSON_DICT_FIELDS:
            if field in result and isinstance(result[field], (list, dict, set)):
                result[field] = json.dumps(result[field], ensure_ascii=False)
        return result

    def _deserialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Parse JSON columns back to Python objects."""
        return row_to_dict(row)

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create with JSON serialization + FTS5 indexing."""
        data = self._serialize(data)
        result = super().create(data)
        # Index in FTS
        self._index_fts(result["uuid"])
        return self._deserialize_row(result)

    def update(self, uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update with JSON serialization + FTS5 reindexing."""
        data = self._serialize(data)
        result = super().update(uuid, data)
        # Re-index in FTS
        self._reindex_fts(uuid)
        return self._deserialize_row(result)

    def delete(self, uuid: str, soft: bool = True) -> None:
        """Delete entry, removing from FTS if hard delete."""
        if not soft:
            # Remove from FTS first
            self._remove_from_fts(uuid)
        super().delete(uuid, soft)

    def get(self, uuid: str) -> dict[str, Any] | None:
        """Get entry with JSON deserialization."""
        row = super().get(uuid)
        if not row:
            return None
        return self._deserialize_row(row)

    def list(
        self,
        order_by: str = "kreita_je",
        desc: bool = True,
        limit: int = None,
    ) -> list[dict[str, Any]]:
        """List entries with JSON deserialization."""
        rows = super().list(order_by=order_by, desc=desc, limit=limit)
        return [self._deserialize_row(row) for row in rows]

    def find_by_titolo(self, titolo: str) -> dict[str, Any] | None:
        """Find entry by case-insensitive title."""
        row = self.db.execute_one(
            "SELECT * FROM encik WHERE LOWER(titolo) = LOWER(?)", (titolo,)
        )
        if not row:
            return None
        return self._deserialize_row(row)

    def find_by_uuid_prefix(self, prefix: str) -> list[dict[str, Any]]:
        """Find entries whose UUID starts with prefix."""
        rows = self.db.execute(
            "SELECT * FROM encik WHERE uuid LIKE ?", (f"{prefix}%",)
        )
        return [self._deserialize_row(row) for row in rows]

    def search_fts(
        self,
        query: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search entries using FTS5 full-text search."""
        try:
            # Escape special FTS characters and wrap query terms
            escaped = query.replace('"', '""')
            fts_query = f'"{escaped}"'
            
            rows = self.db.execute(
                """
                SELECT encik.* FROM encik
                JOIN encik_fts ON encik.rowid = encik_fts.rowid
                WHERE encik_fts MATCH ?
                LIMIT ?
                """,
                (fts_query, limit),
            )
            return [self._deserialize_row(row) for row in rows]
        except Exception:
            # Fallback to LIKE search if FTS fails
            return self.search("titolo", query, case_sensitive=False)[:limit]

    def search_like(
        self,
        query: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search entries using LIKE (fallback)."""
        pattern = f"%{query}%"
        rows = self.db.execute(
            """
            SELECT * FROM encik
            WHERE titolo LIKE ? OR difinio LIKE ? OR enhavo LIKE ?
            LIMIT ?
            """,
            (pattern, pattern, pattern, limit),
        )
        return [self._deserialize_row(row) for row in rows]

    def _index_fts(self, uuid: str) -> None:
        """Index a single entry in FTS5."""
        entry = self.get(uuid)
        if not entry:
            return
        
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO encik_fts (uuid, titolo, terminologio, difinio, difinoj, enhavo)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["uuid"],
                    entry.get("titolo", ""),
                    json.dumps(entry.get("terminologio", {}), ensure_ascii=False),
                    entry.get("difinio", ""),
                    json.dumps(entry.get("difinoj", {}), ensure_ascii=False),
                    entry.get("enhavo", ""),
                ),
            )

    def _reindex_fts(self, uuid: str) -> None:
        """Re-index a single entry in FTS5."""
        self._remove_from_fts(uuid)
        self._index_fts(uuid)

    def _remove_from_fts(self, uuid: str) -> None:
        """Remove an entry from FTS5."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM encik_fts WHERE uuid = ?", (uuid,))

    def count(self) -> int:
        """Return total entry count."""
        row = self.db.execute_one("SELECT COUNT(*) AS cnt FROM encik")
        return row.get("cnt", 0) if row else 0


def get_service() -> EncikService:
    """Get the singleton EncikService for encik table."""
    global _encik_service
    if _encik_service is None:
        _encik_service = EncikService(get_db())
    return _encik_service


__all__ = ["EncikService", "get_service"]