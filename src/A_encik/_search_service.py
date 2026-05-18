"""Search/find mixin for EncikService — all search and query methods."""

from __future__ import annotations

import json
import re
from typing import Any


class SearchMixin:
    """Mixin providing search and query methods for EncikService.

    Depends on ``self`` having: ``db`` (SQLiteDB), ``table`` (str),
    ``_serialize()``, ``_deserialize_row()``, ``_ensure_terminologio_search()``.
    """

    # ── Find by title / terminologio ──────────────────────────────────────────

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

    # ── Full-text search ──────────────────────────────────────────────────────

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

        # Phase 1: SQL filter -> K matching entries with prefix boost + recency
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

        # Phase 2: Python ranking on K entries only (O(K * F) approx 500 ops)
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

        # Sort: recency desc -> compactness asc -> frequency desc
        entries.sort(key=lambda e: (
            e.get("kreita_je", "") or "",
            e.get("_compactness", 10**9),
        ), reverse=True)
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

    # ── Batch / count / semantic search ───────────────────────────────────────

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

    # ── Reconciliation ────────────────────────────────────────────────────────

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

    def fix_latex_escapes(self) -> int:
        """Fix mangled LaTeX backslash escapes in existing entries.

        The old ``escape_latex_style_backslashes`` kept ``\\t`` and ``\\n``
        as valid TOML escapes, causing tomllib to interpret them as tab and
        newline instead of literal backslash+letter. This method scans all
        text fields and restores ``\\t`` (tab) → ``\\textbackslash t``
        and ``\\n`` (newline) → ``\\textbackslash n`` in LaTeX contexts.

        Returns:
            Number of entries fixed.
        """
        count = 0
        rows = self.db.execute("SELECT * FROM encik")
        for row in rows:
            entry = self._deserialize_row(row)
            entry_uuid = entry.get("uuid", "")
            if not entry_uuid:
                continue

            needs_update = False
            text_fields: dict[str, Any] = {
                "difinio": entry.get("difinio", ""),
                "enhavo": entry.get("enhavo", ""),
            }

            # difinoj dict values
            dif = entry.get("difinoj") or {}
            for lang, val in dif.items():
                if isinstance(val, str) and ("\t" in val or "\n" in val):
                    cleaned = val.replace("\t", "\\t").replace("\n", "\\n")
                    if cleaned != val:
                        dif[lang] = cleaned
                        needs_update = True

            # terminologio dict values
            term = entry.get("terminologio") or {}
            for lang, val in term.items():
                if isinstance(val, str) and ("\t" in val or "\n" in val):
                    cleaned = val.replace("\t", "\\t").replace("\n", "\\n")
                    if cleaned != val:
                        term[lang] = cleaned
                        needs_update = True

            # difinio and enhavo
            for field_name in ("difinio", "enhavo"):
                val = entry.get(field_name, "")
                if isinstance(val, str) and ("\t" in val or "\n" in val):
                    text_fields[field_name] = (
                        val.replace("\t", "\\t").replace("\n", "\\n")
                    )
                    needs_update = True

            if not needs_update:
                continue

            # Persist changes
            updates = {}
            if needs_update:
                # dif and term are mutated in-place (same objects as entry dicts)
                updates["difinoj"] = json.dumps(dif, ensure_ascii=False)
                updates["terminologio"] = json.dumps(term, ensure_ascii=False)
                updates["terminologio_search"] = self._ensure_terminologio_search(term)
            for fn in ("difinio", "enhavo"):
                if text_fields[fn] != entry.get(fn, ""):
                    updates[fn] = text_fields[fn]

            if updates:
                set_clauses = [f"{k} = ?" for k in updates]
                values = list(updates.values()) + [entry_uuid]
                self.db.execute(
                    f"UPDATE {self.table} SET {', '.join(set_clauses)} WHERE uuid = ?",
                    values,
                )
                count += 1

        return count


__all__ = ["SearchMixin"]
