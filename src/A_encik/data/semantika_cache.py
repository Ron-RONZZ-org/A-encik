"""Semantic arc cache for Wikidata property lookups.

Three-layer cache: SQLite (fast) -> CSV files (human-curated) -> Wikidata API (fallback).
Always queries in English for consistency (Wikidata lacks non-English descriptions for many entries).

Split into sub-modules for maintainability:
    - ``_cache_db``: DB init, seeding, connection
    - ``_cache_lookup``: Three-layer lookup logic
    - ``_cache_api``: Wikidata API query with circuit breaker
    - ``_cache_negative``: Negative cache (tombstones)
    - ``_cache_store``: Batch store and keyword generation
    - ``_cache_maintenance``: Invalidation, stats, DB repair
"""

from __future__ import annotations

from A_encik.data._cache_db import (
    CREATE_SEMANTIKA_CACHE,
    CACHE_TTL_DAYS,
    CACHE_TTL_SECONDS,
    init_cache_table,
)
from A_encik.data._cache_lookup import lookup_property
from A_encik.data._cache_maintenance import invalidate_old_entries, get_cache_stats

__all__ = [
    "CREATE_SEMANTIKA_CACHE",
    "CACHE_TTL_DAYS",
    "CACHE_TTL_SECONDS",
    "init_cache_table",
    "lookup_property",
    "invalidate_old_entries",
    "get_cache_stats",
]
