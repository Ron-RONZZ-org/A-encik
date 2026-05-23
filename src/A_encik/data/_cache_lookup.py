"""Cache lookup logic for semantika cache — three-layer lookup."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from A import warning as _warn
from A.core.wikidata import COMMON_PROPERTIES
from A_encik.data._cache_db import _get_db
from A_encik.data._cache_maintenance import _repair_attempted, _try_repair_db


def lookup_property(keyword: str) -> dict[str, Any]:
    """Search for Wikidata properties matching an English keyword.

    Three-layer lookup: SQLite cache -> CSV files -> Wikidata API.
    Returns all matching properties so the LLM can choose the right one.

    Args:
        keyword: English keyword describing the property (e.g. "profession")

    Returns:
        Dict with either {"results": [...]} or {"error": "..."}
    """
    # Normalize keyword (lowercase, strip)
    kw = keyword.strip().lower()

    # 0. Pre-seeded common properties (fastest, no DB/CSV/API)
    if kw in COMMON_PROPERTIES:
        return {"results": COMMON_PROPERTIES[kw]}

    # 1. Check SQLite cache (LIKE substring match)
    cache_results = _check_db_cache(kw)
    if cache_results:
        return {"results": cache_results}

    # 2. Check CSV files
    csv_results = _check_csv_files(kw)
    if csv_results:
        from A_encik.data._cache_store import _batch_store
        _batch_store(csv_results, source="csv")
        return {"results": csv_results}

    # 3. Query Wikidata API
    from A_encik.data._cache_negative import _check_negative_cache
    if _check_negative_cache(kw):
        return {"results": [], "message": f"No Wikidata properties found for '{keyword}'"}

    from A_encik.data._cache_api import _query_wikidata_api
    api_results = _query_wikidata_api(kw)
    if api_results:
        from A_encik.data._cache_store import _batch_store
        _batch_store(api_results, source="api")
        return {"results": api_results}

    # API failed or no results — fall back to any stale cache entry
    stale = _check_db_cache(kw[:3])  # Broader search: first 3 chars
    if stale:
        return {"results": stale, "source": "stale_cache"}
    return {"results": [], "message": f"No Wikidata properties found for '{keyword}'"}


def _check_db_cache(keyword: str) -> list[dict] | None:
    """Search SQLite cache with LIKE substring match.

    Args:
        keyword: Normalized English keyword

    Returns:
        List of cached results or None (None = cache miss or DB error)
    """
    try:
        db = _get_db()
        rows = db.execute(
            """SELECT property_id, label_en, label_eo, description, source, fetched_at
               FROM semantika_cache
               WHERE keyword LIKE ? OR label_en LIKE ? OR description LIKE ?
               ORDER BY hit_count DESC, fetched_at DESC
               LIMIT 15""",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
        )
        if rows:
            for row in rows:
                db.execute(
                    "UPDATE semantika_cache SET hit_count = hit_count + 1 WHERE property_id = ?",
                    (row["property_id"],),
                )
            return [
                {
                    "id": r["property_id"],
                    "label": r["label_en"],
                    "label_eo": r.get("label_eo", ""),
                    "description": r.get("description", ""),
                }
                for r in rows
            ]
        return None
    except sqlite3.DatabaseError as e:
        msg = str(e).lower()
        if "disk is full" in msg:
            raise  # Disk full — re-raise, repair won't help
        if not _repair_attempted:
            _warn(f"SQLite cache unavailable: {e}")
        _try_repair_db()
        return None
    except sqlite3.Error as e:
        if not _repair_attempted:
            _warn(f"SQLite cache error: {e}")
        return None
        if rows:
            # Update hit counts
            for row in rows:
                db.execute(
                    "UPDATE semantika_cache SET hit_count = hit_count + 1 WHERE property_id = ?",
                    (row["property_id"],),
                )
        return [
            {
                "id": r["property_id"],
                "label": r["label_en"],
                "label_eo": r.get("label_eo", ""),
                "description": r.get("description", ""),
            }
            for r in rows
        ]
    return None


def _check_csv_files(keyword: str) -> list[dict] | None:
    """Search human-curated CSV semantika files for matching entries.

    Args:
        keyword: Normalized English keyword

    Returns:
        List of matching property dicts or None
    """
    try:
        from A_encik.semantika.config import load_semantika_groups
        groups = load_semantika_groups()
        results = []
        seen_ids = set()
        for group_name, entries in groups.items():
            for entry in entries:
                ligilo = entry.get("ligilo", "")
                arko = entry.get("arko", "")
                valoro = entry.get("valoro", "")
                # Match against label/ID/description
                if keyword in ligilo.lower() or keyword in arko.lower() or keyword in valoro.lower():
                    prop_id = _extract_property_id(ligilo)
                    if prop_id and prop_id not in seen_ids:
                        seen_ids.add(prop_id)
                        results.append({
                            "id": prop_id,
                            "label": arko,
                            "description": valoro,
                            "label_eo": "",
                        })
        return results if results else None
    except ImportError:
        return None


def _extract_property_id(ligilo: str) -> str | None:
    """Extract Wikidata property ID from ligilo string.

    Handles formats: "wdt:P106", "P106", "wd:P106"
    """
    match = re.search(r'(?:wdt:|wd:)?(P\d+)', ligilo)
    return match.group(1) if match else None
