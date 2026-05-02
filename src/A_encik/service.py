"""Service layer for A-encik using CRUDService with FTS5."""

from __future__ import annotations

import json
from typing import Any

from A.core.service import CRUDService

from A_encik.data.storage import get_db, row_to_dict, ENCIK_FTS_CONFIG

_encik_service: EncikService | None = None


class EncikService(CRUDService):
    """Extended CRUDService for encik with JSON columns and FTS5.

    Features:
    - JSON serialization for complex columns
    - Core FTS5 full-text search indexing (inherited from CRUDService)
    - Title and UUID prefix lookups
    - Custom search methods
    """

    def __init__(self, db):
        """Initialize EncikService with FTS5 from core."""
        super().__init__(db, "encik", fts_config=ENCIK_FTS_CONFIG)

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
        """Create with JSON serialization. FTS indexing handled by parent."""
        data = self._serialize(data)
        result = super().create(data)
        return self._deserialize_row(result)

    def update(self, uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update with JSON serialization. FTS reindexing handled by parent."""
        data = self._serialize(data)
        result = super().update(uuid, data)
        return self._deserialize_row(result)

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
        filters: dict[str, str] | None = None,
        order_by: str = "relevance",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Search entries using core FTS5 full-text search."""
        rows = super().search_fts(query, filters, order_by, limit, offset)
        return [self._deserialize_row(row) for row in rows]

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

    def count(self) -> int:
        """Return total entry count."""
        row = self.db.execute_one("SELECT COUNT(*) AS cnt FROM encik")
        return row.get("cnt", 0) if row else 0

    def search_semantika(
        self,
        conditions: list[dict[str, Any]],
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search entries by semantic conditions.

        Loads all entries and filters in Python (semantika is a JSON column).
        For large datasets, consider adding a dedicated index.

        Args:
            conditions: Parsed conditions from
                :func:`A_encik.semantika.search.parse_semantika_serci_conditions`.
            limit: Max results.

        Returns:
            List of matching entries (deserialized).
        """
        from A_encik.semantika.search import entry_matches_semantika_conditions

        rows = self.db.execute("SELECT * FROM encik LIMIT ?", (limit * 2,))
        # We fetch a bit extra since filtering may reduce results
        all_entries = [self._deserialize_row(row) for row in rows]
        matching = [
            e for e in all_entries
            if entry_matches_semantika_conditions(e, conditions)
        ]
        return matching[:limit]


def get_service() -> EncikService:
    """Get the singleton EncikService for encik table."""
    global _encik_service
    if _encik_service is None:
        _encik_service = EncikService(get_db())
    return _encik_service


__all__ = ["EncikService", "get_service"]