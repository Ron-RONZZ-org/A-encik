"""Negative cache (tombstone for "no results") for semantika cache."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone


def _store_negative_cache(keyword: str, ttl_seconds: int = 3600) -> None:
    """Store a tombstone entry so repeated lookups for the same keyword
    skip the API until the TTL expires."""
    from A_encik.data._cache_db import _get_db
    try:
        db = _get_db()
        expiry = (datetime.now(timezone.utc).timestamp() + ttl_seconds)
        db.execute(
            """INSERT OR REPLACE INTO semantika_cache
               (keyword, property_id, label_en, description, source, fetched_at)
               VALUES (?, '_NEGATIVE_', '', '', 'negative_cache', ?)""",
            (keyword, expiry),
        )
    except sqlite3.Error:
        pass  # Cache write failures are non-fatal


def _check_negative_cache(keyword: str) -> bool:
    """Check if a keyword has a negative cache entry that hasn't expired."""
    from A_encik.data._cache_db import _get_db
    try:
        db = _get_db()
        row = db.execute_one(
            "SELECT fetched_at FROM semantika_cache WHERE keyword = ? AND property_id = '_NEGATIVE_'",
            (keyword,),
        )
        if row:
            try:
                expiry = float(row["fetched_at"])
                return time.time() < expiry
            except (ValueError, TypeError):
                pass
        return False
    except sqlite3.Error:
        return False
