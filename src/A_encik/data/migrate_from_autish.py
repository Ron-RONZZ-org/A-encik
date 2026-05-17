"""Migration from autish encik.db to A-encik.

Run with:
    from A_encik.data.migrate_from_autish import migrate
    
    result = migrate()
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from A_encik.data.storage import get_db


# Legacy autish data path
_LEGACY_DIR = Path.home() / ".local" / "share" / "autish"
_LEGACY_DB = _LEGACY_DIR / "encik.db"


def migrate() -> dict:
    """Migrate entries from autish encik.db to A-encik.
    
    Returns:
        Dict with migration results
    """
    if not _LEGACY_DB.exists():
        return {"skipped": True, "reason": "No legacy data found"}
    
    # Connect to A-encik DB
    target = get_db()
    
    migrated = 0
    errors = []
    
    # Connect to legacy DB
    legacy = sqlite3.connect(str(_LEGACY_DB))
    legacy.row_factory = sqlite3.Row
    
    # Migrate entries
    rows = legacy.execute("SELECT * FROM encik").fetchall()
    
    for row in rows:
        try:
            # Parse JSON fields
            terminologio = _parse_json_field(row, "terminologio")
            difinoj = _parse_json_field(row, "difinoj")
            superklaso = _parse_json_field(row, "superklaso")
            ligilo = _parse_json_field(row, "ligilo")
            fonto = _parse_json_field(row, "fonto")
            citajo = _parse_json_field(row, "citajo")
            datumo = _parse_json_field(row, "datumo")
            semantika = _parse_json_field(row, "semantika")
            
            # Backfill terminologio from legacy titolo if empty
            if not terminologio and row.get("titolo"):
                terminologio = {"eo": str(row["titolo"])}

            # Insert into A-encik, preserving timestamps
            target.execute(
                """INSERT INTO encik (
                    uuid, difinio, terminologio, difinoj, enhavo,
                    superklaso, ligilo, fonto, citajo, datumo, semantika,
                    kreita_je, modifita_je
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["uuid"],
                    row["difinio"],
                    json.dumps(terminologio),
                    json.dumps(difinoj),
                    row["enhavo"] or "",
                    json.dumps(superklaso),
                    json.dumps(ligilo),
                    json.dumps(fonto),
                    json.dumps(citajo),
                    json.dumps(datumo),
                    json.dumps(semantika),
                    row["kreita_je"],
                    row["modifita_je"],
                ),
            )
            
            migrated += 1
            
        except Exception as e:
            try:
                errors.append(f"{row['uuid']}: {e}")
            except Exception:
                errors.append(f"unknown: {e}")
    
    legacy.close()
    
    return {
        "source_rows": len(rows),
        "migrated_rows": migrated,
        "errors": errors,
    }


def _parse_json_field(row: sqlite3.Row, field: str) -> dict | list:
    """Parse a JSON field."""
    val = row[field]
    if val:
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            pass
    return {} if field in ("terminologio", "difinoj", "datumo") else []


__all__ = ["migrate"]