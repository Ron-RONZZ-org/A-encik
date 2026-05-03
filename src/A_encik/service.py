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

    # ──────────────────────────────────────────────────────────────────────────
    # Knowledge Graph Methods
    # ──────────────────────────────────────────────────────────────────────────

    def get_subclasses(
        self,
        uuid: str,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """Find all entries with superklaso pointing to this entry (BFS).

        Args:
            uuid: Root UUID to find subclasses for
            max_depth: Maximum traversal depth

        Returns:
            List of subclass entries with depth info
        """
        entries = self.list()
        children_map: dict[str, set[str]] = {}

        # Build parent -> children map
        for entry in entries:
            entry_uuid = entry.get("uuid")
            superklaso = entry.get("superklaso", [])
            if isinstance(superklaso, str):
                superklaso = [superklaso]
            for parent_uuid in superklaso:
                if parent_uuid not in children_map:
                    children_map[parent_uuid] = set()
                children_map[parent_uuid].add(entry_uuid)

        # BFS traversal
        results: list[dict[str, Any]] = []
        visited: set[str] = {uuid}
        queue: list[tuple[str, int]] = [(uuid, 0)]

        while queue:
            current_uuid, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            children = children_map.get(current_uuid, set())
            for child_uuid in children:
                if child_uuid not in visited:
                    visited.add(child_uuid)
                    child_entry = self.get(child_uuid)
                    if child_entry:
                        results.append({
                            "entry": child_entry,
                            "depth": depth + 1,
                        })
                    queue.append((child_uuid, depth + 1))

        return results

    def get_superclasses(
        self,
        uuid: str,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """Find all entries that this entry points to via superklaso (BFS).

        Args:
            uuid: Root UUID to find superclasses for
            max_depth: Maximum traversal depth

        Returns:
            List of superclass entries with depth info
        """
        entry = self.get(uuid)
        if not entry:
            return []

        results: list[dict[str, Any]] = []
        visited: set[str] = {uuid}
        queue: list[tuple[str, int]] = []

        # Start with direct superclasses
        superklaso = entry.get("superklaso", [])
        if isinstance(superklaso, str):
            superklaso = [superklaso]
        for parent_uuid in superklaso:
            if parent_uuid:
                queue.append((parent_uuid, 1))

        # BFS
        while queue:
            current_uuid, depth = queue.pop(0)
            if current_uuid in visited or depth > max_depth:
                continue
            visited.add(current_uuid)

            current_entry = self.get(current_uuid)
            if current_entry:
                results.append({
                    "entry": current_entry,
                    "depth": depth,
                })

            # Add its superclasses
            current_super = current_entry.get("superklaso", [])
            if isinstance(current_super, str):
                current_super = [current_super]
            for parent_uuid in current_super:
                if parent_uuid and parent_uuid not in visited:
                    queue.append((parent_uuid, depth + 1))

        return results

    def get_siblings(
        self,
        uuid: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find entries that share a superklaso with this entry.

        Args:
            uuid: Entry UUID
            limit: Max results

        Returns:
            List of sibling entries
        """
        entry = self.get(uuid)
        if not entry:
            return []

        my_superklaso = entry.get("superklaso", [])
        if isinstance(my_superklaso, str):
            my_superklaso = [my_superklaso]
        my_superklaso = set(my_superklaso)

        if not my_superklaso:
            return []

        siblings: list[dict[str, Any]] = []
        all_entries = self.list()

        for e in all_entries:
            if e.get("uuid") == uuid:
                continue

            e_super = e.get("superklaso", [])
            if isinstance(e_super, str):
                e_super = [e_super]
            e_super_set = set(e_super)

            if my_superklaso & e_super_set:  # Intersection
                siblings.append(e)
                if len(siblings) >= limit:
                    break

        return siblings

    def get_linked_graph(
        self,
        uuid: str,
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """Get full graph of related entries (subclasses, superclasses, ligiloj).

        Args:
            uuid: Root UUID
            max_depth: Maximum traversal depth

        Returns:
            Dict with 'nodes' and 'edges' for visualization
        """
        entry = self.get(uuid)
        if not entry:
            return {"nodes": [], "edges": []}

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        visited: set[str] = {uuid}

        # Add root node
        nodes.append({
            "uuid": uuid,
            "titolo": entry.get("titolo", ""),
            "depth": 0,
        })

        # BFS
        queue: list[tuple[str, int, str]] = []  # (uuid, depth, relation_type)

        # Add superklaso edges
        superklaso = entry.get("superklaso", [])
        if isinstance(superklaso, str):
            superklaso = [superklaso]
        for parent_uuid in superklaso:
            if parent_uuid:
                queue.append((parent_uuid, 1, "superklaso"))

        # Add ligilo edges
        ligilo = entry.get("ligilo", [])
        for link in ligilo:
            link_uuid = link if isinstance(link, str) else link[0]
            if link_uuid:
                queue.append((link_uuid, 1, "ligilo"))

        while queue:
            current_uuid, depth, rel_type = queue.pop(0)
            if current_uuid in visited or depth > max_depth:
                continue
            visited.add(current_uuid)

            current_entry = self.get(current_uuid)
            if current_entry:
                nodes.append({
                    "uuid": current_uuid,
                    "titolo": current_entry.get("titolo", ""),
                    "depth": depth,
                })
                edges.append({
                    "from": uuid if depth == 1 else "",  # Simplified
                    "to": current_uuid,
                    "type": rel_type,
                })

                # Add its connections
                current_super = current_entry.get("superklaso", [])
                if isinstance(current_super, str):
                    current_super = [current_super]
                for parent_uuid in current_super:
                    if parent_uuid and parent_uuid not in visited:
                        queue.append((parent_uuid, depth + 1, "superklaso"))

                current_lig = current_entry.get("ligilo", [])
                for link in current_lig:
                    link_uuid = link if isinstance(link, str) else link[0]
                    if link_uuid and link_uuid not in visited:
                        queue.append((link_uuid, depth + 1, "ligilo"))

        return {"nodes": nodes, "edges": edges}


def get_service() -> EncikService:
    """Get the singleton EncikService for encik table."""
    global _encik_service
    if _encik_service is None:
        _encik_service = EncikService(get_db())
    return _encik_service


__all__ = ["EncikService", "get_service"]