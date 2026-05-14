"""Service layer for A-encik using CRUDService with FTS5."""

from __future__ import annotations

import json
import re
from typing import Any

from A.core.service import CRUDService
from A.core.linking import sync_links_for_entry, remove_entry_links

from A_encik.data.storage import get_db, row_to_dict, ENCIK_FTS_CONFIG
from A_encik._time_entry import TimeEntryMixin
from A_encik._graph import GraphMixin
from A_encik._links import LinksMixin

_encik_service: EncikService | None = None


class EncikService(CRUDService, TimeEntryMixin, GraphMixin, LinksMixin):
    """Encik service: CRUD + time entries + graph + links."""

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
        for field in self._JSON_LIST_FIELDS:
            if field in result and isinstance(result[field], (list, dict)):
                result[field] = json.dumps(result[field], ensure_ascii=False)
        for field in self._JSON_DICT_FIELDS:
            if field in result and isinstance(result[field], (list, dict, set)):
                result[field] = json.dumps(result[field], ensure_ascii=False)
        return result

    def _deserialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Parse JSON columns back to Python objects."""
        return row_to_dict(row)

    @staticmethod
    def _ensure_terminologio_search(terminologio: dict[str, str]) -> str:
        """Build folded search string from terminologio dict."""
        from A.utils.normalize import fold_search_text as _fold
        values = [str(v) for v in terminologio.values() if v]
        return " ".join(_fold(v) for v in values)

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create with JSON serialization. FTS indexing handled by parent."""
        term = data.get("terminologio") or {}
        # Backward compat: if titolo is given without terminologio, populate
        if not term and "titolo" in data:
            term = {"eo": str(data["titolo"])}
            data["terminologio"] = term
        data["terminologio_search"] = self._ensure_terminologio_search(term)
        # Backward compat: provide titolo for old schema (will be dropped)
        if "titolo" not in data:
            for lang in ("eo", "en"):
                val = term.get(lang)
                if val:
                    data["titolo"] = str(val)
                    break
            if "titolo" not in data:
                for val in term.values():
                    if val:
                        data["titolo"] = str(val)
                        break
        data = self._serialize(data)
        result = super().create(data)
        entry = self._deserialize_row(result)
        self._sync_links(entry)
        return entry

    def update(self, uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update with JSON serialization. FTS reindexing handled by parent."""
        if "terminologio" in data:
            data["terminologio_search"] = self._ensure_terminologio_search(
                data["terminologio"]
            )
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
        """Sync inline refs from text fields to both A.core.links and entry ligilo.

        Inline semantic links (``[text](#uuid, prop)``) in difinoj/enhavo text
        are parsed and stored in two places:
        1. ``A.core.links`` — cross-module link database (for backlinks)
        2. ``entry["ligilo"]`` — per-entry JSON column (for display in vidi)
        """
        from A.core.references import parse_refs as _parse_refs

        uuid = entry["uuid"]
        ligiloj = entry.get("ligiloj") or []
        if isinstance(ligiloj, str):
            try:
                ligiloj = json.loads(ligiloj) if ligiloj.strip() else []
            except (json.JSONDecodeError, TypeError):
                ligiloj = []

        text_fields: dict[str, Any] = {
            "terminologio": entry.get("terminologio") or {},
            "difinoj": entry.get("difinoj") or {},
        }
        if entry.get("enhavo"):
            text_fields["enhavo"] = entry["enhavo"]
        if entry.get("difinio"):
            text_fields["difinio"] = entry["difinio"]

        # 1. Sync to A.core.links (cross-module backlinks)
        sync_links_for_entry(
            uuid=uuid,
            source_type="encik",
            text_fields=text_fields,
            explicit_links=ligiloj if isinstance(ligiloj, list) else [],
        )

        # 2. Parse inline refs and merge into entry["ligilo"] for display.
        #    This ensures inline semantic links [text](#uuid, prop) appear
        #    in the ligilo section of vidi output with the correct arc type.
        _INLINE_LINK_RE = re.compile(
            r'\[([^\]]*)\]\(#([0-9a-f-]+)\s*(?:,\s*([^)]+))?\)',
            re.IGNORECASE,
        )

        inline_refs: list[dict] = []
        seen_uuids: set[str] = set()
        # Collect existing explicit ligilo UUIDs
        _existing_ligilo = entry.get("ligilo") or []
        if isinstance(_existing_ligilo, list):
            for _item in _existing_ligilo:
                _uid = _item[0] if isinstance(_item, list) else _item
                if isinstance(_uid, str):
                    seen_uuids.add(_uid)

        for _fv in text_fields.values():
            _strings: list[str] = []
            if isinstance(_fv, str):
                _strings = [_fv]
            elif isinstance(_fv, dict):
                _strings = [str(_v) for _v in _fv.values() if isinstance(_v, str)]
            for _s in _strings:
                for _m in _INLINE_LINK_RE.finditer(_s):
                    _ref_uuid = _m.group(2).strip().lower()
                    _ref_tipo = (_m.group(3) or "").strip()
                    # Validate UUID (8+ hex chars)
                    if not _ref_uuid or len(_ref_uuid) < 8 or not all(c in '0123456789abcdef-' for c in _ref_uuid):
                        continue
                    if _ref_uuid not in seen_uuids and _ref_uuid != uuid:
                        seen_uuids.add(_ref_uuid)
                        tipo = f"ec#{_ref_tipo}" if _ref_tipo else "ec#inline"
                        inline_refs.append([_ref_uuid, tipo])

        if inline_refs:
            merged = list(_existing_ligilo) + inline_refs if isinstance(_existing_ligilo, list) else inline_refs
            entry["ligilo"] = merged
            # Persist back to database so ligilo is visible next time
            self.db.execute(
                "UPDATE encik SET ligilo = ? WHERE uuid = ?",
                (json.dumps(merged, ensure_ascii=False), uuid),
            )

    def get(self, uuid: str) -> dict[str, Any] | None:
        """Get entry by UUID with prefix fallback."""
        row = self.db.execute_one(
            "SELECT * FROM encik WHERE uuid LIKE ?", (f"{uuid}%",),
        )
        if row:
            return self._deserialize_row(row)
        return None

    def list(
        self,
        order_by: str = "kreita_je",
        desc: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List entries with pagination."""
        order = "DESC" if desc else "ASC"
        sql = f"SELECT * FROM {self.table} ORDER BY {order_by} {order}"
        if limit:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"
        rows = self.db.execute(sql)
        return [self._deserialize_row(row) for row in rows]

    def find_by_titolo(self, titolo: str) -> dict[str, Any] | None:
        """Find entry where ANY ``terminologio`` value matches (accent-insensitive).

        Searches all ``terminologio.{lang}`` values via the ``terminologio_search``
        column, which contains all values folded and concatenated. This means
        searching ``"Francio"`` finds entries where any language's term matches.
        """
        from A.utils.normalize import fold_search_text as _fold
        folded = _fold(titolo)
        if not folded:
            return None
        row = self.db.execute_one(
            "SELECT * FROM encik WHERE terminologio_search LIKE ? LIMIT 1",
            (f"%{folded}%",),
        )
        if row:
            return self._deserialize_row(row)
        return None

    def find_by_terminologio(
        self, terminologio: dict[str, str]
    ) -> dict[str, Any] | None:
        """Find entry where ANY value in the given terminologio dict matches.

        Used for duplicate detection: pass the parsed ``terminologio`` from
        a .enc file, and this finds any existing entry that has a matching
        term in ANY language.

        Args:
            terminologio: Dict like ``{"eo": "Francio", "en": "France"}``

        Returns:
            First matching entry, or None.
        """
        from A.utils.normalize import fold_search_text as _fold
        values = [v for v in terminologio.values() if v]
        if not values:
            return None
        conditions = " OR ".join(["terminologio_search LIKE ?"] * len(values))
        params = [f"%{_fold(v)}%" for v in values]
        row = self.db.execute_one(
            f"SELECT * FROM {self.table} WHERE {conditions} LIMIT 1",
            params,
        )
        if row:
            return self._deserialize_row(row)
        return None

    def find_by_uuid_prefix(self, prefix: str, limit: int = 10) -> list[dict[str, Any]]:
        """Find entries matching UUID prefix."""
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
        """Full-text search via FTS5."""
        rows = super().search_fts(query, filters, order_by, limit, offset)
        return [self._deserialize_row(row) for row in rows]

    def search_like(
        self,
        query: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """LIKE search — accent-insensitive, matches all terminologio values."""
        from A.utils.normalize import fold_search_text as _fold
        folded = _fold(query)
        if folded:
            rows = self.db.execute(
                "SELECT * FROM encik WHERE terminologio_search LIKE ? LIMIT ?",
                (f"%{folded}%", limit),
            )
            if rows:
                return [self._deserialize_row(row) for row in rows]
        pattern = f"%{query}%"
        rows = self.db.execute(
            "SELECT * FROM encik WHERE difinio LIKE ? OR enhavo LIKE ? LIMIT ?",
            (pattern, pattern, limit),
        )
        return [self._deserialize_row(row) for row in rows]

    def get_many(self, uuids: list[str]) -> dict[str, dict[str, Any]]:
        """Batch-resolve multiple UUIDs in a single query."""
        if not uuids:
            return {}
        placeholders = ", ".join(["?"] * len(uuids))
        sql = f"SELECT * FROM encik WHERE uuid IN ({placeholders})"
        rows = self.db.execute(sql, tuple(uuids))
        return {r["uuid"]: self._deserialize_row(r) for r in rows}

    def count(self) -> int:
        """Return total entry count."""
        row = self.db.execute_one("SELECT COUNT(*) AS cnt FROM encik")
        return row.get("cnt", 0) if row else 0

    def search_semantika(
        self,
        conditions: list[dict[str, Any]],
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search entries by semantic conditions."""
        from A_encik.semantika.search import entry_matches_semantika_conditions
        rows = self.db.execute("SELECT * FROM encik LIMIT ?", (limit * 2,))
        all_entries = [self._deserialize_row(row) for row in rows]
        matching = [
            e for e in all_entries
            if entry_matches_semantika_conditions(e, conditions)
        ]
        return matching[:limit]

    # ── Lifecycle hooks ──────────────────────────────────────────────────────

    def _post_create(self, data: dict[str, Any], result: dict[str, Any]) -> None:
        """Hook called after create — sync bidirectional links."""
        self._sync_bidirectional_relations(result)

    def _post_update(
        self, uuid: str, old_data: dict[str, Any] | None, new_data: dict[str, Any]
    ) -> None:
        """Hook called after update — sync bidirectional links."""
        old_ligilo = (old_data or {}).get("ligilo", [])
        self._sync_bidirectional_relations(new_data, previous_ligilo=old_ligilo)

    def _post_delete(self, uuid: str, data: dict[str, Any] | None, soft: bool) -> None:
        """Hook called after delete — remove stale reverse links."""
        if not soft and data:
            old_ligilo = data.get("ligilo", [])
            self._remove_stale_reverse_links(uuid, old_ligilo)

    def reconcile_all_reverse_links(self) -> int:
        """Manually reconcile all bidirectional links in the database."""
        count = 0
        entries = self.list()
        for entry in entries:
            entry_uuid = entry.get("uuid")
            superklaso = entry.get("superklaso", [])
            if isinstance(superklaso, str):
                superklaso = [superklaso]
            for parent_uuid in superklaso:
                if not parent_uuid:
                    continue
                parent = self.get(parent_uuid)
                if not parent:
                    continue
                ligilo = parent.get("ligilo", [])
                if isinstance(ligilo, str):
                    ligilo = [ligilo]
                needs_add = True
                for link in ligilo:
                    link_uuid = link if isinstance(link, str) else link[0]
                    if link_uuid == entry_uuid:
                        needs_add = False
                        break
                if needs_add:
                    new_ligilo = ligilo + [[entry_uuid, "rdfs:hasSubClass"]]
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
