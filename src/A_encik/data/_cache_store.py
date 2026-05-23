"""Cache storage utilities for semantika cache."""

from __future__ import annotations

import re
import sqlite3


def _batch_store(results: list[dict], source: str = "api") -> None:
    """Store multiple property results in cache.

    Args:
        results: List of property dicts with id, label, description
        source: Origin ("api" or "csv")
    """
    from A_encik.data._cache_db import _get_db, _now_iso
    try:
        db = _get_db()
        now = _now_iso()
        for r in results:
            prop_id = r.get("id", "")
            label = r.get("label", "")
            description = r.get("description", "")
            keywords = _generate_keywords(label, description)
            for kw in keywords:
                db.execute(
                    """INSERT OR IGNORE INTO semantika_cache
                       (keyword, property_id, label_en, description, source, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (kw, prop_id, label, description, source, now),
                )
    except sqlite3.Error:
        pass  # Cache write failures are non-fatal


def _generate_keywords(label: str, description: str) -> list[str]:
    """Generate search keywords from label and description.

    Breaks phrases into individual words and common bigrams.

    Args:
        label: Property label
        description: Property description

    Returns:
        List of keyword strings
    """
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
