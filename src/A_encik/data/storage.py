"""Encik data layer - SQLite storage."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from A.core.paths import data_dir as _data_dir, ensure_dirs as _ensure_dirs
from A.data.base import (
    SQLiteDB,
    backup_db,
    health_check as _health_check,
    repair_db as _core_repair,
    readonly_recover as _core_readonly_recover,
)
from A.data.search import FTSConfig
from A.utils.normalize import fold_search_text

_DATA_DIR: Path = _data_dir()
_DB_FILE: Path = _DATA_DIR / "encik.db"

_CREATE_ENCIK = """
CREATE TABLE IF NOT EXISTS encik (
    uuid        TEXT PRIMARY KEY,
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

    Delegates to ``A.data.base.repair_db()`` for WAL+SHM cleanup and
    VACUUM. If that fails, additionally drops and recreates the
    ``semantika_cache`` table (expendable cache — repopulates from
    CSV/Wikidata).

    Returns:
        True if repair was attempted, False if nothing was needed.
    """
    if _health_check(_DB_FILE):
        return False

    # Core repair: delete WAL/SHM, VACUUM
    if _core_repair(_DB_FILE):
        return True

    # Still broken — drop and recreate semantika_cache
    try:
        _conn = sqlite3.connect(str(_DB_FILE))
        _conn.execute("DROP TABLE IF EXISTS semantika_cache")
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS semantika_cache (
                keyword     TEXT NOT NULL,
                property_id TEXT NOT NULL,
                label_en    TEXT NOT NULL DEFAULT '',
                label_eo    TEXT DEFAULT '',
                description TEXT DEFAULT '',
                source      TEXT DEFAULT 'api',
                fetched_at  TEXT NOT NULL,
                hit_count   INTEGER DEFAULT 1,
                PRIMARY KEY (keyword, property_id)
            )"""
        )
        (_result,) = _conn.execute("PRAGMA quick_check").fetchone()
        _conn.close()
        return _result == "ok"
    except Exception:
        return False


def repair_db() -> bool:
    global _db_instance
    if _db_instance is not None:
        try:
            _db_instance.close()
        except Exception:
            pass
        _db_instance = None
    return _repair_if_corrupted()


def _backup_db() -> None:
    backup_db(_DB_FILE)


def _readonly_recover() -> SQLiteDB | None:
    import tempfile
    tmp = Path(tempfile.mktemp(suffix=".db"))
    try:
        count = _core_readonly_recover(_DB_FILE, tmp)
    except Exception:
        tmp.unlink(missing_ok=True)
        return None
    if count == 0:
        tmp.unlink(missing_ok=True)
        return None
    from A import info as _info, tr_multi as _tr
    _info(_tr(
        "Reakiris {n} enskribojn...",
        "Recovered {n} entries...",
        "Récupéré {n} entrées...",
    ).format(n=count))
    _bak = _DB_FILE.with_suffix(".db.dead")
    import shutil as _su
    _su.move(str(_DB_FILE), str(_bak))
    _su.move(str(tmp), str(_DB_FILE))
    for _sfx in ("-wal", "-shm"):
        (_DB_FILE.parent / (_DB_FILE.name + _sfx)).unlink(missing_ok=True)
    _info(_tr(
        "Reakiris {n} enskribojn (malnova DB: {bak})",
        "Recovered {n} entries (old DB: {bak})",
        "Récupéré {n} entrées (ancienne DB: {bak})",
    ).format(n=count, bak=_bak.name))
    return SQLiteDB(_DB_FILE)


_db_instance: SQLiteDB | None = None
_repair_checked: bool = False  # Only check corruption once per process


def get_db() -> SQLiteDB:
    """Get or create the shared database connection (singleton).

    All callers within the same process share one ``SQLiteDB`` instance,
    which uses one cached SQLite connection. This avoids WAL/SHM conflicts
    that occur when multiple connections access the same database file.
    """
    global _db_instance, _repair_checked

    # Fast path: existing healthy instance (repair checked on first access)
    if _db_instance is not None and _repair_checked:
        return _db_instance

    if not _repair_checked:
        ensure_dirs()
        _repair_if_corrupted()
        _repair_checked = True

        # If repair deleted WAL/SHM while we had a cached connection,
        # close it so the new one starts fresh
        if _db_instance is not None:
            _db_instance.close()
            _db_instance = None

    if _db_instance is None:
        # Backup before any DDL
        _backup_db()
        _db_instance = SQLiteDB(_DB_FILE)

    # Initialize schema and run migrations.
    # If the DB is corrupted these may fail — catch and surface a clear message.
    try:
        # If the FTS table has wrong columns (schema changed), drop it first
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
    except sqlite3.DatabaseError:
        _db_instance.close()
        _db_instance = None
        # Try read-only recovery before giving up
        _ro = _readonly_recover()
        if _ro is not None:
            _db_instance = _ro
        else:
            raise RuntimeError(
                f"Datumbazo estas koruptita. Reakiro ne eblas.\n"
                f"Reimportu de .enc dosieroj: for f in *.enc; do A encik aldoni \"$f\"; done"
            )

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

    # Migration: drop legacy titolo column (now sourced from terminologio)
    if "titolo" in cols:
        # Backfill terminologio from titolo for any old entries that lack it
        from A.utils.normalize import fold_search_text as _fold
        _backfill_rows = db.execute(
            "SELECT uuid, titolo, terminologio FROM encik"
        )
        for _r in _backfill_rows:
            _term_raw = _r["terminologio"]
            if isinstance(_term_raw, str):
                try:
                    _term = json.loads(_term_raw)
                except (json.JSONDecodeError, ValueError):
                    _term = {}
            elif isinstance(_term_raw, dict):
                _term = _term_raw
            else:
                _term = {}
            if not _term and _r.get("titolo"):
                _term = {"eo": str(_r["titolo"])}
                _ts = _fold(str(_r["titolo"]))
                db.execute(
                    "UPDATE encik SET terminologio = ?, terminologio_search = ? WHERE uuid = ?",
                    (json.dumps(_term), _ts, _r["uuid"]),
                )
        # Drop the legacy column and its dependent indexes
        try:
            for _idx in ("idx_encik_titolo_lower", "idx_encik_titolo_fold",
                         "idx_encik_titolo_fold_idx"):
                db.execute(f"DROP INDEX IF EXISTS {_idx}")
            db.execute("ALTER TABLE encik DROP COLUMN titolo")
            # Also drop titolo_fold if it still exists (another legacy column)
            try:
                db.execute("ALTER TABLE encik DROP COLUMN titolo_fold")
            except Exception:
                pass  # May already be gone
        except Exception as _ex:
            from A import warning as _warn
            _warn(f"Unable to drop legacy 'titolo' column ({_ex}). "
                  "Entry creation must include 'titolo' for backward compat.")

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
        d["terminologio"] = {}
    # Synthesize entry["titolo"] from terminologio for backward-compat display code
    if "titolo" not in d:
        _term = d.get("terminologio") or {}
        for _val in _term.values():
            if _val:
                d["titolo"] = str(_val)
                break
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


__all__ = ["ensure_dirs", "get_db", "migrate_db", "repair_db", "row_to_dict", "ENCIK_FTS_CONFIG"]