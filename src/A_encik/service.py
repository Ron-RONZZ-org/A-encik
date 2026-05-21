"""Service layer for A-encik using CRUDService with FTS5."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from A.core.service import CRUDService
from A.core.linking import sync_links_for_entry, remove_entry_links

from A_encik.data.storage import get_db, row_to_dict, ENCIK_FTS_CONFIG
from A_encik._time_entry import TimeEntryMixin
from A_encik._graph import GraphMixin
from A_encik._links import LinksMixin
from A_encik._search_service import SearchMixin

_encik_service: EncikService | None = None


class EncikService(SearchMixin, CRUDService, TimeEntryMixin, GraphMixin, LinksMixin):
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
        data["terminologio_search"] = self._ensure_terminologio_search(term)
        try:
            data = self._serialize(data)
            result = super().create(data)
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Datumbaza konstricefkizo (kodo={exc.sqlite_errorcode}): {exc}"
            ) from exc
        entry = self._deserialize_row(result)
        self._sync_links(entry)                                           # rebuild outgoing links
        self._sync_bidirectional_relations(entry, previous_ligilo=[])     # create reverse links
        return entry

    def update(self, uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update with JSON serialization. FTS reindexing handled by parent."""
        # Save old ligilo BEFORE update (for bidirectional diff)
        old = self.get(uuid)
        old_ligilo = (old or {}).get("ligilo", [])
        if isinstance(old_ligilo, str):
            old_ligilo = []

        if "terminologio" in data:
            data["terminologio_search"] = self._ensure_terminologio_search(
                data["terminologio"]
            )
        data = self._serialize(data)
        try:
            result = super().update(uuid, data)
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Datumbaza konstricefkizo (kodo={exc.sqlite_errorcode}): {exc}"
            ) from exc
        entry = self._deserialize_row(result)
        self._sync_links(entry)                                           # rebuild outgoing links
        self._sync_bidirectional_relations(entry, previous_ligilo=old_ligilo)  # diff + sync reverse
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

        # 2. Rebuild entry["ligilo"] from current text and explicit ligilo.
        #    Start with any explicit ligilo from the update data (if present),
        #    then overlay with inline refs from text fields. This ensures that
        #    changes to inline links in the .enc file are reflected exactly.
        _INLINE_LINK_RE = re.compile(
            r'\[([^\]]*)\]\(#([0-9a-f-]+)\s*(?:,\s*([^)]+))?\)',
            re.IGNORECASE,
        )

        # Seed map with explicit ligilo from the update data (not old DB)
        _ligilo_map: dict[str, str] = {}
        _explicit = entry.get("ligilo") or []
        if isinstance(_explicit, str):
            try:
                _explicit = json.loads(_explicit)
            except (json.JSONDecodeError, ValueError):
                _explicit = []
        for _item in (_explicit if isinstance(_explicit, list) else []):
            _uid = _item[0] if isinstance(_item, list) else _item
            _tipo = str(_item[1]) if isinstance(_item, list) and len(_item) > 1 else ""
            if isinstance(_uid, str) and len(_uid) >= 8:
                _ligilo_map[_uid] = _tipo

        # Overlay inline refs from text (last occurrence wins)
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
                    _ref_tipo = re.sub(r":\s+", ":", _ref_tipo)
                    if not _ref_uuid or len(_ref_uuid) < 8:
                        continue
                    if _ref_uuid == uuid:
                        continue
                    _ligilo_map[_ref_uuid] = f"ec#{_ref_tipo}" if _ref_tipo else "ec#related"

        # Persist rebuilt ligilo
        _new_ligilo = [[uid, t] for uid, t in _ligilo_map.items()]
        entry["ligilo"] = _new_ligilo
        self.db.execute(
            "UPDATE encik SET ligilo = ? WHERE uuid = ?",
            (json.dumps(_new_ligilo, ensure_ascii=False), uuid),
        )

        # Rebuild ligilo list from map
        _new_ligilo = [[uid, tipo] for uid, tipo in _ligilo_map.items()]
        entry["ligilo"] = _new_ligilo
        self.db.execute(
            "UPDATE encik SET ligilo = ? WHERE uuid = ?",
            (json.dumps(_new_ligilo, ensure_ascii=False), uuid),
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

    # ── Lifecycle hooks (no-ops — handled in create/update directly) ────────

    def _post_create(self, data: dict[str, Any], result: dict[str, Any]) -> None:
        pass

    def _post_update(
        self, uuid: str, old_data: dict[str, Any] | None, new_data: dict[str, Any]
    ) -> None:
        pass

    def _post_delete(self, uuid: str, data: dict[str, Any] | None, soft: bool) -> None:
        """Hook called after delete — remove stale reverse links."""
        if not soft and data:
            old_ligilo = data.get("ligilo", [])
            self._remove_stale_reverse_links(uuid, old_ligilo)


def get_service() -> EncikService:
    """Get the singleton EncikService for encik table."""
    global _encik_service
    if _encik_service is None:
        _encik_service = EncikService(get_db())
    return _encik_service


__all__ = ["EncikService", "get_service"]
