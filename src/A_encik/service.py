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
        # Hard fallback: ensure titolo is always set even if all
        # terminologio values are empty. titolo is NOT NULL in the DB.
        if "titolo" not in data:
            data["titolo"] = "sen-titolo"
        try:
            data = self._serialize(data)
            result = super().create(data)
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Datumbaza konstricefkizo (kodo={exc.sqlite_errorcode}): {exc}"
            ) from exc
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
        try:
            result = super().update(uuid, data)
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Datumbaza konstricefkizo (kodo={exc.sqlite_errorcode}): {exc}"
            ) from exc
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

        Uses a two-pass approach:
        1. Fast SQL ``LIKE`` on the concatenated ``terminologio_search`` column
           to get candidates.
        2. Python verification that at least one folded query term matches a
           COMPLETE folded terminologio value (not just a substring). This
           avoids false positives like ``"tax"`` matching ``"taxonomy"``.

        Args:
            terminologio: Dict like ``{"eo": "Francio", "en": "France"}``

        Returns:
            First matching entry, or None.
        """
        from A.utils.normalize import fold_search_text as _fold
        values = [v for v in terminologio.values() if v]
        if not values:
            return None

        # Pass 1: fast SQL LIKE on concatenated column
        conditions = " OR ".join(["terminologio_search LIKE ?"] * len(values))
        params = [f"%{_fold(v)}%" for v in values]
        candidates = self.db.execute(
            f"SELECT * FROM {self.table} WHERE {conditions} LIMIT 20",
            params,
        )

        # Pass 2: Python verification — exact (folded) match against each
        # individual terminologio value, not substrings.
        folded_queries = {_fold(v) for v in values}
        for row in candidates:
            entry = self._deserialize_row(row)
            entry_values = [
                str(v) for v in entry.get("terminologio", {}).values() if v
            ]
            entry_folded = {_fold(v) for v in entry_values}
            if folded_queries & entry_folded:
                return entry

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

    def search_ranked(
        self,
        query: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Ranked search across all text fields.

        All operations are O(K log K) where K = results count (=10-50),
        never O(N) where N = total entries (up to 10⁴+).

        Ranking factors:
        1. **Title prefix** (SQL): entries whose ``terminologio`` starts
           with the query are ranked first (``CASE WHEN LIKE 'prefix%'``).
        2. **Match frequency** (Python): number of text fields the query
           appears in across terminologio, difinoj, enhavo, difinio.
        3. **Compactness** (Python): how close the query appears to the
           start of each field (lower = better).
        4. **Recency** (SQL): ``ORDER BY kreita_je DESC``.

        All Python scoring runs only on the K results returned by SQL,
        never on the full database.

        Args:
            query: Search text.
            limit: Max results.

        Returns:
            Ranked list of matching entries.
        """
        from A.utils.normalize import fold_search_text as _fold
        folded = _fold(query)
        if not folded:
            return []

        # Phase 1: SQL filter → K matching entries with prefix boost + recency
        pattern = f"%{folded}%"
        prefix = f"{folded}%"
        rows = self.db.execute(
            """SELECT *, (
                CASE WHEN terminologio_search LIKE ? THEN 0 ELSE 1 END
            ) AS _title_prefix
            FROM encik
            WHERE terminologio_search LIKE ?
            ORDER BY _title_prefix ASC, kreita_je DESC
            LIMIT ?""",
            (prefix, pattern, limit),
        )
        entries = [self._deserialize_row(row) for row in rows]

        if not entries:
            rows = self.db.execute(
                "SELECT * FROM encik WHERE difinio LIKE ? OR enhavo LIKE ? ORDER BY kreita_je DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            )
            entries = [self._deserialize_row(row) for row in rows]

        if len(entries) <= 1:
            return entries

        # Phase 2: Python ranking on K entries only (O(K * F) ≅ ~500 ops)
        for e in entries:
            texts: list[str] = []
            term = e.get("terminologio") or {}
            texts.extend(str(v) for v in term.values() if v)
            dif = e.get("difinoj") or {}
            texts.extend(str(v) for v in dif.values() if v)
            if e.get("enhavo"):
                texts.append(str(e["enhavo"]))
            if e.get("difinio"):
                texts.append(str(e["difinio"]))

            # Match frequency: count fields containing the query
            freq = sum(1 for t in texts if folded in _fold(t))
            e["_frequency"] = freq

            # Compactness: minimum index of query in any field
            best = 10**9
            for t in texts:
                idx = _fold(t).find(folded)
                if 0 <= idx < best:
                    best = idx
            e["_compactness"] = best

        # Sort: recency desc → compactness asc → frequency desc
        # kreita_je is TEXT (ISO format, e.g. "2026-05-12T12:35:03").
        # Negating a string raises TypeError, so use reverse=True and
        # negate the other keys instead.
        entries.sort(key=lambda e: (
            e.get("kreita_je", "") or "",                  # newer first (reverse)
            e.get("_compactness", 10**9),                  # tighter match first
        ), reverse=True)
        # Re-sort stably by frequency (descending) to keep top matches
        entries.sort(key=lambda e: e.get("_frequency", 0), reverse=True)

        return entries[:limit]

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
                "SELECT * FROM encik WHERE terminologio_search LIKE ? ORDER BY kreita_je DESC LIMIT ?",
                (f"%{folded}%", limit),
            )
            if rows:
                return [self._deserialize_row(row) for row in rows]
        pattern = f"%{query}%"
        rows = self.db.execute(
            "SELECT * FROM encik WHERE difinio LIKE ? OR enhavo LIKE ? ORDER BY kreita_je DESC LIMIT ?",
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

    def reconcile_all_computed_fields(self) -> int:
        """Rebuild `ligilo` and `terminologio_search` for EVERY entry.

        Reads each entry from the database, re-parses inline refs from
        text fields to rebuild ``entry["ligilo"]``, and recomputes
        ``terminologio_search`` from the current ``terminologio``.
        Then persists both back to the database.

        This is the bulk fix for entries that were imported with older
        code that didn't properly sync inline links or search data.

        Returns:
            Number of entries updated.
        """
        rows = self.db.execute("SELECT * FROM encik")
        count = 0
        for row in rows:
            entry = self._deserialize_row(row)
            entry_uuid = entry.get("uuid", "")
            if not entry_uuid:
                continue

            # Recompute terminologio_search
            term = entry.get("terminologio") or {}
            ts = self._ensure_terminologio_search(term)
            updates: dict[str, Any] = {"terminologio_search": ts}

            # Rebuild ligilo from inline refs
            text_fields: dict[str, Any] = {
                "difinoj": entry.get("difinoj") or {},
                "enhavo": entry.get("enhavo") or "",
            }
            if entry.get("difinio"):
                text_fields["difinio"] = entry["difinio"]

            _INLINE_LINK_RE = re.compile(
                r'\[([^\]]*)\]\(#([0-9a-f-]+)\s*(?:,\s*([^)]+))?\)',
                re.IGNORECASE,
            )
            ligilo_map: dict[str, str] = {}
            for _fv in text_fields.values():
                _vals: list[str] = []
                if isinstance(_fv, str):
                    _vals = [_fv]
                elif isinstance(_fv, dict):
                    _vals = [str(_v) for _v in _fv.values() if isinstance(_v, str)]
                for _s in _vals:
                    for _m in _INLINE_LINK_RE.finditer(_s):
                        _ru = _m.group(2).strip().lower()
                        _rt = (_m.group(3) or "").strip()
                        _rt = re.sub(r":\s+", ":", _rt)
                        if _ru and len(_ru) >= 8 and _ru != entry_uuid:
                            ligilo_map[_ru] = f"ec#{_rt}" if _rt else "ec#related"

            new_ligilo = [[u, t] for u, t in ligilo_map.items()]
            updates["ligilo"] = json.dumps(new_ligilo, ensure_ascii=False)

            # Persist
            set_clauses = [f"{k} = ?" for k in updates]
            values = list(updates.values()) + [entry_uuid]
            self.db.execute(
                f"UPDATE {self.table} SET {', '.join(set_clauses)} WHERE uuid = ?",
                values,
            )
            count += 1

        return count

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
