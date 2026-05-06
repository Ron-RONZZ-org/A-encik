"""Semantic arc cache for Wikidata property lookups.

Three-layer cache: SQLite (fast) → CSV files (human-curated) → Wikidata API (fallback).
Always queries in English for consistency (Wikidata lacks non-English descriptions for many entries).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from A import info, warning as _warn


# SQL for cache table
CREATE_SEMANTIKA_CACHE = """
CREATE TABLE IF NOT EXISTS semantika_cache (
    keyword     TEXT NOT NULL,
    property_id TEXT NOT NULL,
    label_en    TEXT NOT NULL DEFAULT '',
    label_eo    TEXT DEFAULT '',
    description TEXT DEFAULT '',
    source      TEXT DEFAULT 'api',
    fetched_at  TEXT NOT NULL,
    hit_count   INTEGER DEFAULT 1,
    PRIMARY KEY (keyword, property_id)
);
"""

# Default TTL for cache entries (seconds)
CACHE_TTL_DAYS = 7
CACHE_TTL_SECONDS = CACHE_TTL_DAYS * 86400


def init_cache_table(db=None) -> None:
    """Ensure the cache table exists.

    Args:
        db: SQLiteDB instance (provided by storage.py to avoid circular imports)
    """
    if db is None:
        db = _get_db()
    db.execute(CREATE_SEMANTIKA_CACHE)


def _get_db():
    """Get database connection (lazy import to avoid circular deps)."""
    from A_encik.data.storage import get_db as _db
    return _db()


def _now_iso() -> str:
    """Get current timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


# ── Cache lookup ────────────────────────────────────────────────────────────


def lookup_property(keyword: str) -> dict[str, Any]:
    """Search for Wikidata properties matching an English keyword.

    Three-layer lookup: SQLite cache → CSV files → Wikidata API.
    Returns all matching properties so the LLM can choose the right one.

    Args:
        keyword: English keyword describing the property (e.g. "profession")

    Returns:
        Dict with either {"results": [...]} or {"error": "..."}
    """
    # Normalize keyword (lowercase, strip)
    kw = keyword.strip().lower()

    # 1. Check SQLite cache (LIKE substring match)
    cache_results = _check_db_cache(kw)
    if cache_results:
        return {"results": cache_results}

    # 2. Check CSV files
    csv_results = _check_csv_files(kw)
    if csv_results:
        _batch_store(csv_results, source="csv")
        return {"results": csv_results}

    # 3. Query Wikidata API
    api_results = _query_wikidata_api(kw)
    if api_results:
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
        List of cached results or None
    """
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
    import re
    match = re.search(r'(?:wdt:|wd:)?(P\d+)', ligilo)
    return match.group(1) if match else None


def _query_wikidata_api(keyword: str, retries: int = 2) -> list[dict] | None:
    """Query Wikidata API for properties matching keyword.

    Always queries with English priority. Retries on failure.

    Args:
        keyword: English keyword
        retries: Number of retry attempts (default 2)

    Returns:
        List of property dicts or None
    """
    for attempt in range(1, retries + 2):  # initial + retries
        try:
            from A_encik.semantika.wikidata import wikidata_search_properties
            results = wikidata_search_properties(keyword, languages=["en", "eo", "fr"])
            if results:
                return [
                    {
                        "id": _extract_property_id(r.get("ligilo", "")) or r.get("ligilo", ""),
                        "label": r.get("etikedo", ""),
                        "description": r.get("priskribo", ""),
                        "label_eo": "",
                    }
                    for r in results
                    if _extract_property_id(r.get("ligilo", ""))
                ]
            return None  # API succeeded but no results
        except ImportError:
            return None
        except Exception as e:
            if attempt <= retries:
                import time
                _warn(f"Wikidata API retry {attempt}/{retries} for '{keyword}': {e}")
                time.sleep(2.0)
            else:
                _warn(f"Wikidata API query failed for '{keyword}': {e}")
                return None
    return None


# ── Cache storage ────────────────────────────────────────────────────────────


def _batch_store(results: list[dict], source: str = "api") -> None:
    """Store multiple property results in cache.

    Args:
        results: List of property dicts with id, label, description
        source: Origin ("api" or "csv")
    """
    db = _get_db()
    now = _now_iso()
    for r in results:
        prop_id = r.get("id", "")
        label = r.get("label", "")
        description = r.get("description", "")
        # Generate keywords from label and description for better cache hits
        keywords = _generate_keywords(label, description)
        for kw in keywords:
            db.execute(
                """INSERT OR IGNORE INTO semantika_cache
                   (keyword, property_id, label_en, description, source, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (kw, prop_id, label, description, source, now),
            )


def _generate_keywords(label: str, description: str) -> list[str]:
    """Generate search keywords from label and description.

    Breaks phrases into individual words and common bigrams.

    Args:
        label: Property label
        description: Property description

    Returns:
        List of keyword strings
    """
    import re
    words = set()
    text = f"{label} {description}".lower()
    # Individual words (3+ chars)
    for w in re.findall(r"[a-z]{3,}", text):
        words.add(w)
    # Bigrams
    tokens = re.findall(r"[a-z]{3,}", text)
    for i in range(len(tokens) - 1):
        words.add(f"{tokens[i]} {tokens[i+1]}")
    return list(words)


# ── Cache maintenance ────────────────────────────────────────────────────────


def invalidate_old_entries(ttl_days: int = CACHE_TTL_DAYS) -> int:
    """Remove cache entries older than TTL.

    Args:
        ttl_days: Max age in days

    Returns:
        Number of removed entries
    """
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()
    db = _get_db()
    db.execute("DELETE FROM semantika_cache WHERE fetched_at < ? AND source = 'api'", (cutoff,))
    # Count remaining csv-sourced entries
    remaining = db.execute_one("SELECT COUNT(*) AS c FROM semantika_cache")
    return remaining["c"] if remaining else 0


def get_cache_stats() -> dict[str, int]:
    """Get cache statistics.

    Returns:
        Dict with total, api_sourced, csv_sourced
    """
    db = _get_db()
    total = db.execute_one("SELECT COUNT(*) AS c FROM semantika_cache")
    by_source = db.execute(
        "SELECT source, COUNT(*) AS c FROM semantika_cache GROUP BY source"
    )
    stats = {"total": total["c"] if total else 0}
    for row in by_source:
        stats[row["source"]] = row["c"]
    return stats


__all__ = [
    "init_cache_table",
    "lookup_property",
    "invalidate_old_entries",
    "get_cache_stats",
]
