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
    titolo      TEXT,
    difinio     TEXT NOT NULL DEFAULT '',
    terminologio TEXT NOT NULL DEFAULT '{}',
    terminologio_search TEXT NOT NULL DEFAULT '',
    difinoj     TEXT NOT NULL DEFAULT '{}',
    enhavo      TEXT NOT NULL DEFAULT '',
    superklaso  TEXT NOT NULL DEFAULT '[]',
    ligilo      TEXT NOT NULL DEFAULT '[]',
    fonto       TEXT NOT NULL DEFAULT '[]',
    citajo      TEXT NOT NULL DEFAULT '[]',
    datumo      TEXT NOT NULL DEFAULT '{}',
    semantika   TEXT NOT NULL DEFAULT '[]',
    ligiloj     TEXT NOT NULL DEFAULT '[]',
    kreita_je   TEXT NOT NULL,
    modifita_je TEXT NOT NULL
);
"""

_CREATE_ENCIK_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_encik_uuid_prefix ON encik(substr(uuid, 1, 8));
CREATE INDEX IF NOT EXISTS idx_encik_kreita_je ON encik(kreita_je);
CREATE INDEX IF NOT EXISTS idx_encik_terminologio_search ON encik(terminologio_search);
CREATE INDEX IF NOT EXISTS idx_encik_difinio_lower ON encik(LOWER(difinio));
"""



def ensure_dirs() -> None:
    """Ensure data directory exists."""
    _ensure_dirs()


def _repair_if_corrupted() -> bool:
    """Check and repair database if corrupted.

    Purges stale WAL+SHM files and rebuilds the FTS5 table if needed.
    The FTS5 virtual table can retain internal corruption even after
    WAL cleanup — the only fix is to drop and recreate it.

    Returns:
        True if repair was attempted, False if nothing was needed.
    """
    if not _DB_FILE.exists():
        return False

    # Quick, read-only check first. If the DB is healthy, don't touch
    # WAL/SHM at all — only delete them if quick_check fails.
    try:
        _conn = sqlite3.connect(f"file:{_DB_FILE}?immutable=1", uri=True)
        (_result,) = _conn.execute("PRAGMA quick_check").fetchone()
        _conn.close()
        if _result == "ok":
            return False
    except Exception:
        pass

    # quick_check failed — delete WAL+SHM and retry
    for _suffix in ("-wal", "-shm"):
        _DB_FILE.with_name(_DB_FILE.name + _suffix).unlink(missing_ok=True)

    try:
        _conn = sqlite3.connect(str(_DB_FILE))
        (_result,) = _conn.execute("PRAGMA quick_check").fetchone()
        _conn.close()
        return _result == "ok"
    except Exception:
        return False


def repair_db() -> bool:
    """Attempt to repair a corrupted database.

    Closes the singleton connection, purges stale WAL/SHM files,
    and runs integrity check. The next ``get_db()`` call will
    create a fresh connection.

    Returns:
        True if repair succeeded, False if DB is irrecoverable.
    """
    global _db_instance
    if _db_instance is not None:
        try:
            _db_instance.close()
        except Exception:
            pass
        _db_instance = None
    return _repair_if_corrupted()


_db_instance: SQLiteDB | None = None

def get_db() -> SQLiteDB:
    """Get or create the shared database connection (singleton).

    All callers within the same process share one ``SQLiteDB`` instance,
    which uses one cached SQLite connection. This avoids WAL/SHM conflicts
    that occur when multiple connections access the same database file.
    """
    global _db_instance
    if _db_instance is not None and not _repair_if_corrupted():
        return _db_instance

    ensure_dirs()
    _repair_if_corrupted()

    _db_instance = SQLiteDB(_DB_FILE)

    # If the FTS table has wrong columns (schema changed), drop it first
    # using a fresh connection to avoid WAL state conflicts with the
    # cached connection that will be used for subsequent DDL.
    _fts_name = ENCIK_FTS_CONFIG.fts_table
    try:
        _fts_row = _db_instance.execute_one(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (_fts_name,)
        )
        if _fts_row:
            _fts_sql = _fts_row.get("sql", "")
            _expected = set(ENCIK_FTS_CONFIG.fts_columns)
            _actual = {c for c in ENCIK_FTS_CONFIG.fts_columns if c in _fts_sql}
            if _actual != _expected:
                _db_instance.close()
                with SQLiteDB(_DB_FILE).raw_connection() as _raw:
                    _raw.execute(f"DROP TABLE IF EXISTS {_fts_name}")
                    _raw.commit()
                _db_instance = SQLiteDB(_DB_FILE)
    except Exception:
        _db_instance = SQLiteDB(_DB_FILE)

    _db_instance.execute(_CREATE_ENCIK)
    for stmt in _CREATE_ENCIK_INDEXES.strip().split(";"):
        if stmt.strip():
            _db_instance.execute(stmt)
    migrate_db(_db_instance)
    # Init semantika cache table (lazy import avoids circular dep)
    from A_encik.data.semantika_cache import init_cache_table as _init_cache
    _init_cache(_db_instance)

    # Reset service singleton so it picks up the fresh DB
    import A_encik.service as _svc
    _svc._encik_service = None

    return _db_instance


# FTS5 configuration for encik full-text search
ENCIK_FTS_CONFIG = FTSConfig(
    table="encik",
    fts_columns=["terminologio_search", "difinio", "enhavo"],
    filter_columns=[],
    normalize={
        "terminologio_search": fold_search_text,
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
    if "ligiloj" not in cols:
        db.execute(
            "ALTER TABLE encik ADD COLUMN ligiloj TEXT NOT NULL DEFAULT '[]'"
        )
    if "terminologio_search" not in cols:
        db.execute(
            "ALTER TABLE encik ADD COLUMN terminologio_search TEXT NOT NULL DEFAULT ''"
        )
        # Populate for existing entries from terminologio JSON
        from A.utils.normalize import fold_search_text as _fold
        rows = db.execute("SELECT uuid, terminologio FROM encik")
        for r in rows:
            raw = r["terminologio"]
            if isinstance(raw, str):
                try:
                    term = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    term = {}
            elif isinstance(raw, dict):
                term = raw
            else:
                term = {}
            values = [str(v) for v in term.values() if v]
            folded = " ".join(_fold(v) for v in values)
            db.execute(
                "UPDATE encik SET terminologio_search = ? WHERE uuid = ?",
                (folded, r["uuid"]),
            )

    # Create index after ensuring column exists
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_encik_terminologio_search ON encik(terminologio_search)"
    )


def row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert an encik table row to a plain dict, parsing JSON columns."""
    d = dict(row)
    # Parse list-type JSON columns
    for field in ("superklaso", "ligilo", "fonto", "citajo", "ligiloj", "source"):
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
                if field == "semantika":
                    pass  # Keep raw string — custom format, not JSON
                else:
                    d[field] = {}
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