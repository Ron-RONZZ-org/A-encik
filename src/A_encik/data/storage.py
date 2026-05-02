"""Encik data layer - SQLite storage."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from A import ensure_dirs as _ensure_dirs
from A.data.base import SQLiteDB

_DATA_DIR: Path = Path.home() / ".local" / "share" / "A"
_DB_FILE: Path = _DATA_DIR / "encik.db"

_CREATE_ENCIK = """
CREATE TABLE IF NOT EXISTS encik (
    uuid TEXT PRIMARY KEY,
    titolo TEXT NOT NULL,
    teksto TEXT NOT NULL DEFAULT '',
    lingvo TEXT NOT NULL DEFAULT 'en',
    kategorio TEXT NOT NULL DEFAULT '',
    temo TEXT NOT NULL DEFAULT '',
    fako TEXT NOT NULL DEFAULT '',
    substofo TEXT NOT NULL DEFAULT '',
    autoro TEXT NOT NULL DEFAULT '',
    fonto TEXT NOT NULL DEFAULT '',
    loko TEXT NOT NULL DEFAULT '',
    dato TEXT NOT NULL DEFAULT '',
    ligiloj TEXT NOT NULL DEFAULT '[]',
    supreklaso TEXT NOT NULL DEFAULT '',
    subklasoj TEXT NOT NULL DEFAULT '[]',
    kreita_je TEXT NOT NULL,
    modifita_je TEXT NOT NULL
);
"""

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_encik_titolo ON encik(titolo);
CREATE INDEX IF NOT EXISTS idx_encik_lingvo ON encik(lingvo);
CREATE INDEX IF NOT EXISTS idx_encik_kategorio ON encik(kategorio);
CREATE INDEX IF NOT EXISTS idx_encik_subklasoj ON encik(subklasoj);
CREATE INDEX IF NOT EXISTS idx_encik_supreklaso ON encik(supreklaso);
"""


def ensure_dirs() -> None:
    """Ensure data directory exists."""
    _ensure_dirs(_DATA_DIR)


def get_db() -> SQLiteDB:
    """Get database connection."""
    ensure_dirs()
    db = SQLiteDB(_DB_FILE)
    db.execute(_CREATE_ENCIK)
    for stmt in _CREATE_INDEXES.strip().split(";"):
        if stmt.strip():
            db.execute(stmt)
    return db


__all__ = ["ensure_dirs", "get_db"]