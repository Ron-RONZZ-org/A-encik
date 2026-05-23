"""Reconciliation/repair mixin for EncikService — data repair methods."""

from __future__ import annotations

import json
import re
from typing import Any


class ReconMixin:
    """Mixin providing reconciliation and repair methods for EncikService.

    Depends on ``self`` having: ``db`` (SQLiteDB), ``table`` (str),
    ``_deserialize_row()``, ``_ensure_terminologio_search()``, ``list()``,
    ``get()``, ``_reverse_tipo()``.
    """

    # ── Reconciliation ────────────────────────────────────────────────────────

    def reconcile_all_computed_fields(self) -> int:
        """Rebuild `ligilo` and `terminologio_search` for EVERY entry.

        Reads each entry from the database, re-parses inline refs from
        text fields to rebuild ``entry["ligilo"]``, and recomputes
        ``terminologio_search`` from the current ``terminologio``.
        Then persists both back to the database.

        Also repairs a known corruption from a previous version of
        ``fix_unquoted_uuids`` that inserted double quotes inside
        markdown link labels (``["word"](#uuid)`` instead of
        ``[word](#uuid)``).

        This is the bulk fix for entries that were imported with older
        code that didn't properly sync inline links or search data.

        Returns:
            Number of entries updated.
        """
        # Regex to fix corrupted quotes inside markdown link labels.
        # Old bug: fix_unquoted_uuids turned [word](#uuid) into ["word"](#uuid)
        _FIX_QUOTED_LABEL = re.compile(
            r'\["([^"]+)"([^\]]*)\]\(#',
        )

        rows = self.db.execute("SELECT * FROM encik")
        count = 0
        for row in rows:
            entry = self._deserialize_row(row)
            entry_uuid = entry.get("uuid", "")
            if not entry_uuid:
                continue

            updates: dict[str, Any] = {}

            # Repair corrupted quotes in text fields + rebuild ligilo
            text_fields: dict[str, Any] = {
                "difinoj": entry.get("difinoj") or {},
                "enhavo": entry.get("enhavo") or "",
            }
            if entry.get("difinio"):
                text_fields["difinio"] = entry["difinio"]

            for field_name in ("difinoj", "difinio", "enhavo"):
                raw = text_fields.get(field_name)
                if not raw:
                    continue
                if isinstance(raw, dict):
                    repaired: dict[str, str] = {}
                    for lang, text in raw.items():
                        if isinstance(text, str) and _FIX_QUOTED_LABEL.search(text):
                            repaired[lang] = _FIX_QUOTED_LABEL.sub(
                                r"[\1\2](#", text,
                            )
                        else:
                            repaired[lang] = text
                    if repaired != raw:
                        text_fields[field_name] = repaired
                        updates[field_name] = json.dumps(repaired, ensure_ascii=False)
                elif isinstance(raw, str) and _FIX_QUOTED_LABEL.search(raw):
                    fixed = _FIX_QUOTED_LABEL.sub(r"[\1\2](#", raw)
                    text_fields[field_name] = fixed
                    updates[field_name] = fixed

            # Recompute terminologio_search
            term = entry.get("terminologio") or {}
            ts = self._ensure_terminologio_search(term)
            updates["terminologio_search"] = ts

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
        """Rebuild ALL reverse links from every entry's ligilo.

        Iterates all entries, reads their per-entry ligilo (which was rebuilt
        from inline refs by ``reconcile_all_computed_fields``), and creates
        reverse links in each target entry. This ensures that when entry A
        links to entry B (via any link type), B gets a reverse link back to A.

        Returns:
            Number of reverse links created.
        """
        import json

        count = 0
        entries = self.list()

        # Build a map: target_uuid → [(source_uuid, tipo)] for all forward links
        reverse_map: dict[str, list[tuple[str, str | None]]] = {}
        for entry in entries:
            source_uuid = entry.get("uuid", "")
            if not source_uuid:
                continue

            # Collect all links from ligilo
            ligilo = entry.get("ligilo") or []
            if isinstance(ligilo, str):
                try:
                    ligilo = json.loads(ligilo)
                except (json.JSONDecodeError, ValueError):
                    ligilo = []

            for link in (ligilo or []):
                target_uuid = link[0] if isinstance(link, list) else link
                tipo = str(link[1]) if isinstance(link, list) and len(link) >= 2 else None
                if not target_uuid:
                    continue
                reverse_map.setdefault(target_uuid, []).append((source_uuid, tipo))

            # Also handle superklaso as rdfs:subClassOf links
            superklaso = entry.get("superklaso", [])
            if isinstance(superklaso, str):
                superklaso = [superklaso]
            for parent_uuid in superklaso:
                if not parent_uuid:
                    continue
                reverse_map.setdefault(parent_uuid, []).append((source_uuid, "rdfs:subClassOf"))

        # For each target entry, ensure reverse links exist
        for target_uuid, sources in reverse_map.items():
            target = self.get(target_uuid)
            if not target:
                continue

            existing_ligilo = target.get("ligilo") or []
            if isinstance(existing_ligilo, str):
                try:
                    existing_ligilo = json.loads(existing_ligilo)
                except (json.JSONDecodeError, ValueError):
                    existing_ligilo = []
            existing_uuids = {
                (link[0] if isinstance(link, list) else link).lower()
                for link in (existing_ligilo or [])
            }

            new_links = 0
            for source_uuid, tipo in sources:
                if source_uuid.lower() in existing_uuids:
                    continue
                reverse_tipo = self._reverse_tipo(tipo)
                existing_ligilo.append([source_uuid, reverse_tipo])
                new_links += 1

            if new_links > 0:
                self.db.execute(
                    "UPDATE encik SET ligilo = ? WHERE uuid = ?",
                    (
                        json.dumps(existing_ligilo, ensure_ascii=False),
                        target["uuid"],
                    ),
                )
                count += new_links

        return count

    def fix_latex_escapes(self) -> int:
        """Fix mangled LaTeX backslash escapes in existing entries.

        The old ``escape_latex_style_backslashes`` kept ``\\t`` as a valid
        TOML escape, causing tomllib to interpret it as tab instead of
        literal backslash+letter. This method scans all text fields and
        restores tab (0x09) → ``\\t``.

        NOTE: Does NOT handle ``\\n`` — real newlines (0x0A) in multiline
        TOML strings are intentional line breaks, not mangled escapes.

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
                if isinstance(val, str) and "\t" in val:
                    cleaned = val.replace("\t", "\\t")
                    if cleaned != val:
                        dif[lang] = cleaned
                        needs_update = True

            # terminologio dict values
            term = entry.get("terminologio") or {}
            for lang, val in term.items():
                if isinstance(val, str) and "\t" in val:
                    cleaned = val.replace("\t", "\\t")
                    if cleaned != val:
                        term[lang] = cleaned
                        needs_update = True

            # difinio and enhavo
            for field_name in ("difinio", "enhavo"):
                val = entry.get(field_name, "")
                if isinstance(val, str) and "\t" in val:
                    text_fields[field_name] = val.replace("\t", "\\t")
                    needs_update = True

            if not needs_update:
                continue

            # Persist changes
            updates = {}
            if needs_update:
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

    def undo_newline_damage(self) -> int:
        """Revert newline damage from earlier version of ``fix_latex_escapes``.

        The initial implementation wrongly replaced real newlines (0x0A)
        with literal ``\\n`` (two characters). This method replaces
        ``\\n`` → real newline in all text fields.

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

            # difinoj dict values — replace literal \n with real newline
            dif = entry.get("difinoj") or {}
            for lang, val in dif.items():
                if isinstance(val, str) and "\\n" in val:
                    cleaned = val.replace("\\n", "\n")
                    if cleaned != val:
                        dif[lang] = cleaned
                        needs_update = True

            # terminologio dict values
            term = entry.get("terminologio") or {}
            for lang, val in term.items():
                if isinstance(val, str) and "\\n" in val:
                    cleaned = val.replace("\\n", "\n")
                    if cleaned != val:
                        term[lang] = cleaned
                        needs_update = True

            # difinio and enhavo
            for field_name in ("difinio", "enhavo"):
                val = entry.get(field_name, "")
                if isinstance(val, str) and "\\n" in val:
                    text_fields[field_name] = val.replace("\\n", "\n")
                    needs_update = True

            if not needs_update:
                continue

            updates = {}
            if needs_update:
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


__all__ = ["ReconMixin"]
