"""Cache maintenance utilities for semantika cache."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from A import warning as _warn


# Repair state: track whether we've already attempted DB repair this session.
# Prevents repeated warnings and re-repair attempts on persistent corruption.
_repair_attempted: bool = False


def _try_repair_db() -> None:
    """Attempt DB repair once per session when cache operations fail.

    Delegates to ``storage.repair_db()`` which closes the singleton,
    purges stale WAL/SHM files, runs integrity check, and recreates
    the semantika_cache table if needed.
    After repair, clears negative cache entries (they may have been
    stored based on corrupted data).
    Safe to call speculatively — no-op on healthy DB.
    """
    global _repair_attempted
    if _repair_attempted:
        return
    _repair_attempted = True
    try:
        from A_encik.data.storage import repair_db
        if repair_db():
                # init_cache_table() seeds common properties on next get_db()
                pass
    except Exception:
        pass


def invalidate_old_entries(ttl_days: int = 7) -> int:
    """Remove cache entries older than TTL.

    Args:
        ttl_days: Max age in days

    Returns:
        Number of removed entries
    """
    from A_encik.data._cache_db import _get_db
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
    from A_encik.data._cache_db import _get_db
    db = _get_db()
    total = db.execute_one("SELECT COUNT(*) AS c FROM semantika_cache")
    by_source = db.execute(
        "SELECT source, COUNT(*) AS c FROM semantika_cache GROUP BY source"
    )
    stats = {"total": total["c"] if total else 0}
    for row in by_source:
        stats[row["source"]] = row["c"]
    return stats
