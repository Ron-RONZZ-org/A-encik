"""Database initialization for semantika cache."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from A.data.base import SQLiteDB

from A.core.wikidata import COMMON_PROPERTIES


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
    """Ensure the cache table exists, seeding common properties if empty.

    Handles DB corruption gracefully — if the table is corrupted, it's
    dropped and recreated.

    Args:
        db: SQLiteDB instance (provided by storage.py to avoid circular imports)
    """
    if db is None:
        db = _get_db()
    try:
        db.execute(CREATE_SEMANTIKA_CACHE)
        row = db.execute_one("SELECT COUNT(*) AS cnt FROM semantika_cache")
        if row and row.get("cnt", 0) == 0:
            _seed_common_properties(db)
    except Exception as exc:
        msg = str(exc).lower()
        if "malformed" in msg or "disk i/o" in msg:
            # Cache table is corrupted — drop and recreate
            try:
                db.execute("DROP TABLE IF EXISTS semantika_cache")
                db.execute(CREATE_SEMANTIKA_CACHE)
                _seed_common_properties(db)
            except Exception:
                pass  # Give up; cache repopulates on next lookup
        else:
            raise


def _seed_common_properties(db) -> None:
    """Insert the pre-seeded COMMON_PROPERTIES into the cache table.

    These entries serve as base cache so common lookups never hit the API.
    Marked with source='common' for observability.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    for keyword, results in COMMON_PROPERTIES.items():
        for prop in results:
            try:
                db.execute(
                    """INSERT OR IGNORE INTO semantika_cache
                       (keyword, property_id, label_en, description, source, fetched_at)
                       VALUES (?, ?, ?, ?, 'common', ?)""",
                    (keyword, prop["id"], prop["label"], prop["description"], now),
                )
            except Exception:
                pass


def _get_db():
    """Get the shared database connection from storage (singleton).

    Delegates to ``A_encik.data.storage.get_db()`` which now returns a
    single shared ``SQLiteDB`` instance. This prevents WAL/SHM conflicts
    between multiple connections to the same database file.
    """
    from A_encik.data.storage import get_db as _get_db_impl
    return _get_db_impl()


def _now_iso() -> str:
    """Get current timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()
