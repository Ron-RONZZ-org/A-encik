"""Encik data layer - SQLite storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from A.core.paths import data_dir as _data_dir, ensure_dirs as _ensure_dirs
from A.data.base import SQLiteDB
from A.data.search import FTSConfig
from A.utils.normalize import fold_search_text

_DATA_DIR: Path = _data_dir()
_DB_FILE: Path = _DATA_DIR / "encik.db"

_CREATE_ENCIK = """
CREATE TABLE IF NOT EXISTS encik (
    uuid        TEXT PRIMARY KEY,
    titolo      TEXT NOT NULL,
    difinio     TEXT NOT NULL DEFAULT '',
    terminologio TEXT NOT NULL DEFAULT '{}',
    difinoj     TEXT NOT NULL DEFAULT '{}',
    enhavo      TEXT NOT NULL DEFAULT '',
    superklaso  TEXT NOT NULL DEFAULT '[]',
    ligilo      TEXT NOT NULL DEFAULT '[]',
    fonto       TEXT NOT NULL DEFAULT '[]',
    citajo      TEXT NOT NULL DEFAULT '[]',
    datumo      TEXT NOT NULL DEFAULT '{}',
    semantika   TEXT NOT NULL DEFAULT '[]',
    kreita_je   TEXT NOT NULL,
    modifita_je TEXT NOT NULL
);
"""

_CREATE_ENCIK_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_encik_titolo_lower ON encik(LOWER(titolo));
CREATE INDEX IF NOT EXISTS idx_encik_uuid_prefix ON encik(substr(uuid, 1, 8));
CREATE INDEX IF NOT EXISTS idx_encik_kreita_je ON encik(kreita_je);
"""

def ensure_dirs() -> None:
    """Ensure data directory exists."""
    _ensure_dirs()


def get_db() -> SQLiteDB:
    """Get database connection."""
    ensure_dirs()
    db = SQLiteDB(_DB_FILE)
    db.execute(_CREATE_ENCIK)
    for stmt in _CREATE_ENCIK_INDEXES.strip().split(";"):
        if stmt.strip():
            db.execute(stmt)
    migrate_db(db)
    return db


# FTS5 configuration for encik full-text search
ENCIK_FTS_CONFIG = FTSConfig(
    table="encik",
    fts_columns=["titolo", "difinio", "enhavo"],
    filter_columns=[],
    normalize={
        "titolo": fold_search_text,
        "difinio": fold_search_text,
        "enhavo": fold_search_text,
    },
)


def migrate_db(db: SQLiteDB) -> None:
    """Run database migrations for encik tables."""
    # Get existing columns
    rows = db.execute("PRAGMA table_info(encik)")
    cols: set[str] = set()
    for row in rows:
        # Row may be dict or tuple
        if isinstance(row, dict):
            name = row.get("name")
        else:
            name = row[1] if len(row) > 1 else None
        if name:
            cols.add(name)
    
    # Migration: add missing columns
    if "terminologio" not in cols:
        db.execute(
            "ALTER TABLE encik ADD COLUMN terminologio TEXT NOT NULL DEFAULT '{}'"
        )
    if "difinoj" not in cols:
        db.execute("ALTER TABLE encik ADD COLUMN difinoj TEXT NOT NULL DEFAULT '{}'")
    if "enhavo" not in cols:
        db.execute("ALTER TABLE encik ADD COLUMN enhavo TEXT NOT NULL DEFAULT ''")
    if "fonto" not in cols:
        db.execute("ALTER TABLE encik ADD COLUMN fonto TEXT NOT NULL DEFAULT '[]'")
    if "citajo" not in cols:
        db.execute("ALTER TABLE encik ADD COLUMN citajo TEXT NOT NULL DEFAULT '[]'")
    if "datumo" not in cols:
        db.execute("ALTER TABLE encik ADD COLUMN datumo TEXT NOT NULL DEFAULT '{}'")
    if "semantika" not in cols:
        db.execute(
            "ALTER TABLE encik ADD COLUMN semantika TEXT NOT NULL DEFAULT '[]'"
        )


def row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert an encik table row to a plain dict, parsing JSON columns."""
    d = dict(row)
    # Parse list-type JSON columns
    for field in ("superklaso", "ligilo", "fonto", "citajo", "source"):
        if isinstance(d.get(field), str):
            import json
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, ValueError):
                d[field] = []
    # Parse dict-type JSON columns
    for field in ("terminologio", "difinoj", "datumo", "semantika"):
        if isinstance(d.get(field), str):
            import json
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, ValueError):
                d[field] = {} if field != "semantika" else []
    # Backward compatibility
    if "fonto" not in d and "source" in d:
        d["fonto"] = d.get("source") or []
    if "terminologio" not in d:
        titolo = str(d.get("titolo") or "").strip()
        d["terminologio"] = {"eo": titolo} if titolo else {}
    if "difinoj" not in d:
        difinio = str(d.get("difinio") or "").strip()
        d["difinoj"] = {"eo": difinio} if difinio else {}
    if "enhavo" not in d:
        d["enhavo"] = ""
    if "citajo" not in d:
        d["citajo"] = []
    if "datumo" not in d:
        d["datumo"] = {}
    return d


__all__ = ["ensure_dirs", "get_db", "migrate_db", "row_to_dict", "ENCIK_FTS_CONFIG"]