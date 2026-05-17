"""Encik data layer - SQLite storage."""

from __future__ import annotations

import json
import shutil
import sqlite3
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

    Purges stale WAL+SHM files, then attempts VACUUM rebuild.
    If the semantika_cache table is corrupted, drops and recreates it
    (data loss is acceptable — it repopulates from CSV/Wikidata).

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
        if _result == "ok":
            _conn.close()
            return True
        # Still corrupted — try VACUUM rebuild
        try:
            _conn.execute("VACUUM")
            (_result,) = _conn.execute("PRAGMA quick_check").fetchone()
            if _result == "ok":
                _conn.close()
                return True
        except Exception:
            pass
        # VACUUM didn't fix it — drop and recreate semantika_cache
        try:
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
            pass
        _conn.close()
        return False
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


def _backup_db() -> None:
    """Snapshot the DB file before schema-altering operations.

    Creates ``encik.db.bak`` (overwrites any previous backup).
    No-op if the DB file doesn't exist yet.
    """
    if _DB_FILE.exists():
        _bak = _DB_FILE.with_suffix(".db.bak")
        try:
            shutil.copy2(str(_DB_FILE), str(_bak))
        except Exception:
            pass  # Backup is best-effort


def _readonly_recover() -> SQLiteDB | None:
    """Attempt read-only recovery when DB is corrupted.

    Opens the database in ``mode=ro`` which bypasses write-path corruption.
    If the main ``encik`` table is readable, exports all entries into a
    freshly created ``encik_recovered.db`` and returns a connection to it.

    Returns:
        New ``SQLiteDB`` instance on success, ``None`` if recovery fails.
    """
    try:
        _ro = sqlite3.connect(f"file:{_DB_FILE}?mode=ro", uri=True, timeout=10)
        _tables = _ro.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        _table_names = {t[0] for t in _tables}
        if "encik" not in _table_names:
            _ro.close()
            return None

        _count = _ro.execute("SELECT COUNT(*) FROM encik").fetchone()[0]
        if _count == 0:
            _ro.close()
            return None

        # Build recovery target
        from A import info as _info, tr_multi as _tr
        _info(_tr(
            "Provas reakiri {n} enskribojn...",
            "Attempting to recover {n} entries...",
            "Tentative de récupération de {n} entrées...",
        ).format(n=_count))

        _rec = _DB_FILE.with_name("encik_recovered.db")
        if _rec.exists():
            _rec.unlink()

        _new = sqlite3.connect(str(_rec), timeout=30)
        _new.execute("PRAGMA journal_mode=WAL")

        # Recreate schema from corrupted DB's sqlite_master
        _schema_rows = _ro.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%' "
            "ORDER BY rootpage"
        ).fetchall()
        for (_sql,) in _schema_rows:
            if _sql:
                _new.execute(_sql)

        # Copy rows from each table (encik + supporting)
        for _tn in sorted(_table_names):
            if _tn.startswith("sqlite_") or "_fts" in _tn:
                continue
            try:
                _rows = _ro.execute(f'SELECT * FROM "{_tn}"').fetchall()
                _col_info = _ro.execute(f'PRAGMA table_info("{_tn}")').fetchall()
                _cols = [c[1] for c in _col_info]
                _csv = ", ".join(f'"{c}"' for c in _cols)
                _ph = ", ".join(["?"] * len(_cols))
                for _row in _rows:
                    try:
                        _new.execute(
                            f'INSERT INTO "{_tn}" ({_csv}) VALUES ({_ph})',
                            _row,
                        )
                    except Exception:
                        pass  # Skip problematic rows
            except Exception:
                pass  # Skip corrupted tables

        _new.commit()

        # Verify and return
        _final = _new.execute("SELECT COUNT(*) FROM encik").fetchone()[0]
        _new.close()
        _ro.close()

        if _final > 0:
            # Swap files
            _bak = _DB_FILE.with_suffix(".db.dead")
            shutil.move(str(_DB_FILE), str(_bak))
            shutil.move(str(_rec), str(_DB_FILE))
            for _sfx in ("-wal", "-shm"):
                (_DB_FILE.parent / (_DB_FILE.name + _sfx)).unlink(missing_ok=True)
            _info(_tr(
                "Reakiris {n} enskribojn (malnova DB: {bak})",
                "Recovered {n} entries (old DB: {bak})",
                "Récupéré {n} entrées (ancienne DB: {bak})",
            ).format(n=_final, bak=_bak.name))
            return SQLiteDB(_DB_FILE)
    except Exception:
        pass
    return None


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