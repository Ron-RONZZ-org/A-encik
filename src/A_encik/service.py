"""Service layer for A-encik using CRUDService with FTS5."""

from __future__ import annotations

import json
from typing import Any

from A.core.service import CRUDService
from A.core.linking import sync_links_for_entry, remove_entry_links

from A_encik.data.storage import get_db, row_to_dict, ENCIK_FTS_CONFIG

_encik_service: EncikService | None = None


class EncikService(CRUDService):
    """Extended CRUDService for encik with JSON columns and FTS5.

    Features:
    - JSON serialization for complex columns
    - Core FTS5 full-text search indexing (inherited from CRUDService)
    - Title and UUID prefix lookups
    - Custom search methods
    - Cross-module linking via ligiloj + A.core.linking
    """

    def __init__(self, db):
        """Initialize EncikService with FTS5 from core."""
        super().__init__(db, "encik", fts_config=ENCIK_FTS_CONFIG)

    # JSON columns that need serialization
    _JSON_LIST_FIELDS: tuple[str, ...] = (
        "superklaso", "ligilo", "fonto", "citajo", "semantika", "ligiloj"
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
        from A.utils.normalize import fold_search_text as _fold
        data["titolo_fold"] = _fold(data.get("titolo", ""))
        data = self._serialize(data)
        result = super().create(data)
        entry = self._deserialize_row(result)
        self._sync_links(entry)
        return entry

    def update(self, uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update with JSON serialization. FTS reindexing handled by parent."""
        from A.utils.normalize import fold_search_text as _fold
        if "titolo" in data:
            data["titolo_fold"] = _fold(data["titolo"])
        data = self._serialize(data)
        result = super().update(uuid, data)
        entry = self._deserialize_row(result)
        self._sync_links(entry)
        return entry

    def delete(self, uuid: str, soft: bool = True) -> None:
        """Delete entry and clean up A.core.links."""
        super().delete(uuid, soft=soft)
        if not soft:
            remove_entry_links("encik", uuid)

    def _sync_links(self, entry: dict) -> None:
        """Sync ligiloj + inline refs to A.core.links."""
        uuid = entry["uuid"]
        ligiloj = entry.get("ligiloj") or []
        if isinstance(ligiloj, str):
            try:
                ligiloj = json.loads(ligiloj) if ligiloj.strip() else []
            except (json.JSONDecodeError, TypeError):
                ligiloj = []

        # Collect text fields that may contain vt#/ec# references
        text_fields: dict[str, Any] = {
            "terminologio": entry.get("terminologio") or {},
            "difinoj": entry.get("difinoj") or {},
        }
        if entry.get("enhavo"):
            text_fields["enhavo"] = entry["enhavo"]
        if entry.get("difinio"):
            text_fields["difinio"] = entry["difinio"]

        sync_links_for_entry(
            uuid=uuid,
            source_type="encik",
            text_fields=text_fields,
            explicit_links=ligiloj if isinstance(ligiloj, list) else [],
        )

    def get(self, uuid: str) -> dict[str, Any] | None:
        """Get entry with JSON deserialization and UUID prefix fallback."""
        row = self.db.execute_one(
            "SELECT * FROM encik WHERE uuid LIKE ?",
            (f"{uuid}%",),
        )
        if row:
            return self._deserialize_row(row)
        return None

    def list(
        self,
        order_by: str = "kreita_je",
        desc: bool = True,
        limit: int = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List entries with JSON deserialization and optional pagination.

        Args:
            order_by: Column to order by.
            desc: Descending order if True.
            limit: Max results.
            offset: Number of rows to skip (for pagination).
        """
        order = "DESC" if desc else "ASC"
        sql = f"SELECT * FROM {self.table} ORDER BY {order_by} {order}"
        if limit:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"
        rows = self.db.execute(sql)
        return [self._deserialize_row(row) for row in rows]

    def find_by_titolo(self, titolo: str) -> dict[str, Any] | None:
        """Find entry by case- and accent-insensitive title."""
        from A.utils.normalize import fold_search_text as _fold
        folded = _fold(titolo)
        # Fast path: exact match (indexed via LOWER)
        row = self.db.execute_one(
            "SELECT * FROM encik WHERE LOWER(titolo) = LOWER(?)", (titolo,)
        )
        if row:
            return self._deserialize_row(row)
        # Accent-insensitive: use titolo_fold column
        if folded:
            row = self.db.execute_one(
                "SELECT * FROM encik WHERE titolo_fold = ?", (folded,)
            )
            if row:
                return self._deserialize_row(row)
        return None

    def search_like(
        self,
        query: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search entries using LIKE (fallback), accent-insensitive."""
        from A.utils.normalize import fold_search_text as _fold
        folded = _fold(query)
        # Accent-insensitive search via titolo_fold column
        if folded:
            rows = self.db.execute(
                "SELECT * FROM encik WHERE titolo_fold LIKE ? LIMIT ?",
                (f"%{folded}%", limit),
            )
            if rows:
                return [self._deserialize_row(row) for row in rows]
        # Fallback to raw LIKE
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

    def get_many(self, uuids: list[str]) -> dict[str, dict[str, Any]]:
        """Batch-resolve multiple UUIDs in a single query.

        Args:
            uuids: List of full UUIDs (36 chars each) to resolve.

        Returns:
            Dict mapping each requested UUID to its deserialized entry,
            or an empty dict if none are found. UUIDs not in the database
            are omitted from the result.
        """
        if not uuids:
            return {}
        placeholders = ", ".join(["?"] * len(uuids))
        sql = f"SELECT * FROM encik WHERE uuid IN ({placeholders})"
        rows = self.db.execute(sql, tuple(uuids))
        return {r["uuid"]: self._deserialize_row(r) for r in rows}

    def find_by_uuid_prefix(self, prefix: str, limit: int = 10) -> list[dict[str, Any]]:
        """Find entries whose UUID starts with prefix (uses core CRUD method)."""
        rows = super().find_by_uuid_prefix(prefix, limit=limit)
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

    # ──────────────────────────────────────────────────────────────────────────
    # Bidirectional Link Reconciliation
    # ──────────────────────────────────────────────────────────────────────────

    # Mapping of semantic relations and their inverses
    _REVERSE_MAP: dict[str, str] = {
        "rdfs:subClassOf": "rdfs:hasSubClass",
        "rdfs:hasSubClass": "rdfs:subClassOf",
        "rdf:type": "rdf:hasInstance",
        "rdf:hasInstance": "rdf:type",
        "wdt:P361": "wdt:P527",  # part of -> has parts
        "wdt:P527": "wdt:P361",  # has parts -> part of
        "wdt:P26": "wdt:P26",    # spouse -> spouse (symmetric)
    }

    def _reverse_ligilo(self, tipo: str | None) -> str | None:
        """Get the reverse relation type for a given semantic link type."""
        if not tipo:
            return None
        return self._REVERSE_MAP.get(tipo)

    def _sync_bidirectional_relations(
        self,
        entry: dict[str, Any],
        previous_ligilo: list | None = None,
    ) -> None:
        """Sync bidirectional superklaso/ligilo relations.

        When an entry has superklaso references, automatically add
        reverse ligilo entries in the target entries.

        Args:
            entry: The entry being created/updated
            previous_ligilo: Previous ligilo value (for updates)
        """
        superklaso = entry.get("superklaso", [])
        if isinstance(superklaso, str):
            superklaso = [superklaso]

        # For each superclass, add reverse ligilo
        for parent_uuid in superklaso:
            if not parent_uuid:
                continue

            parent = self.get(parent_uuid)
            if not parent:
                continue

            # Get current ligilo and add reverse
            ligilo = parent.get("ligilo", [])
            if isinstance(ligilo, str):
                ligilo = [ligilo]

            # Check if reverse already exists
            reverse_entry = entry.get("uuid")
            needs_add = True
            for link in ligilo:
                link_uuid = link if isinstance(link, str) else link[0]
                if link_uuid == reverse_entry:
                    needs_add = False
                    break

            if needs_add:
                # Add reverse link as [uuid, "rdfs:hasSubClass"]
                new_ligilo = ligilo + [[reverse_entry, "rdfs:hasSubClass"]]
                self.update(parent_uuid, {"ligilo": new_ligilo})

    def _remove_stale_reverse_links(
        self,
        uuid: str,
        old_ligilo: list,
    ) -> None:
        """Remove reverse links from entries that linked to this one.

        Args:
            uuid: The deleted entry's UUID
            old_ligilo: The ligilo list from before deletion
        """
        # Find entries that might have this uuid in their ligilo
        all_entries = self.list()
        for entry in all_entries:
            ligilo = entry.get("ligilo", [])
            if isinstance(ligilo, str):
                ligilo = [ligilo]

            modified = False
            new_ligilo = []
            for link in ligilo:
                link_uuid = link if isinstance(link, str) else link[0]
                if link_uuid != uuid:
                    new_ligilo.append(link)
                else:
                    modified = True

            if modified:
                self.update(entry["uuid"], {"ligilo": new_ligilo})

    def _post_create(
        self,
        data: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """Hook called after create - sync bidirectional links."""
        self._sync_bidirectional_relations(result)

    def _post_update(
        self,
        uuid: str,
        old_data: dict[str, Any] | None,
        new_data: dict[str, Any],
    ) -> None:
        """Hook called after update - sync bidirectional links."""
        old_ligilo = (old_data or {}).get("ligilo", [])
        self._sync_bidirectional_relations(new_data, previous_ligilo=old_ligilo)

    def _post_delete(
        self,
        uuid: str,
        data: dict[str, Any] | None,
        soft: bool,
    ) -> None:
        """Hook called after delete - remove stale reverse links."""
        if not soft and data:
            old_ligilo = data.get("ligilo", [])
            self._remove_stale_reverse_links(uuid, old_ligilo)

    def reconcile_all_reverse_links(self) -> int:
        """Manually reconcile all bidirectional links in the database.

        Returns:
            Number of links reconciled
        """
        count = 0
        entries = self.list()

        for entry in entries:
            uuid = entry.get("uuid")
            superklaso = entry.get("superklaso", [])
            if isinstance(superklaso, str):
                superklaso = [superklaso]

            # Ensure reverse ligilo exists in all superclasses
            for parent_uuid in superklaso:
                if not parent_uuid:
                    continue

                parent = self.get(parent_uuid)
                if not parent:
                    continue

                ligilo = parent.get("ligilo", [])
                if isinstance(ligilo, str):
                    ligilo = [ligilo]

                # Add reverse if missing
                needs_add = True
                for link in ligilo:
                    link_uuid = link if isinstance(link, str) else link[0]
                    if link_uuid == uuid:
                        needs_add = False
                        break

                if needs_add:
                    new_ligilo = ligilo + [[uuid, "rdfs:hasSubClass"]]
                    self.update(parent_uuid, {"ligilo": new_ligilo})
                    count += 1

        return count


def get_service() -> EncikService:
    """Get the singleton EncikService for encik table."""
    global _encik_service
    if _encik_service is None:
        _encik_service = EncikService(get_db())
    return _encik_service


__all__ = ["EncikService", "get_service"]