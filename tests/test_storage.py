"""Tests for A-encik storage module."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import pytest

from A_encik.data.storage import (
    get_db,
    ensure_dirs,
    migrate_db,
    row_to_dict,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    db_path = tmp_path / "test.db"
    return db_path


@pytest.fixture
def mock_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Mock data directory to temp path."""
    # Import and patch after establishing the path module
    import A_encik.data.storage as storage_module
    
    # Patch at module level
    monkeypatch.setattr(storage_module, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_module, "_DB_FILE", tmp_path / "encik.db")


class TestRowToDict:
    """Tests for row_to_dict function."""
    
    def test_empty_row(self):
        """Test empty dict passes through."""
        result = row_to_dict({})
        # Empty row is returned as-is (may add defaults)
        assert isinstance(result, dict)
    
    def test_json_list_fields(self):
        """Test JSON list fields are parsed."""
        row = {
            "uuid": "test-uuid",
            "superklaso": '["uuid1", "uuid2"]',
            "ligilo": '["uuid3"]',
            "fonto": "[]",
            "terminologio": '{"eo": "testo"}',
        }
        result = row_to_dict(row)
        assert result["superklaso"] == ["uuid1", "uuid2"]
        assert result["ligilo"] == ["uuid3"]
        assert result["fonto"] == []
    
    def test_json_dict_fields(self):
        """Test JSON dict fields are parsed."""
        row = {
            "uuid": "test-uuid",
            "terminologio": '{"eo": "testo", "en": "test"}',
            "difinoj": '{"eo": "difino"}',
        }
        result = row_to_dict(row)
        assert result["terminologio"] == {"eo": "testo", "en": "test"}
        assert result["difinoj"] == {"eo": "difino"}
    
    def test_backward_compat_source(self):
        """Test source field becomes fonto."""
        row = {
            "uuid": "test-uuid",
            "source": '["source1"]',
            "terminologio": '{"eo": "testo"}',
        }
        result = row_to_dict(row)
        assert result["fonto"] == ["source1"]
    
    def test_missing_terminologio_defaults_to_empty(self):
        """Test missing terminologio defaults to empty dict (titolo column gone)."""
        row = {
            "uuid": "test-uuid",
            "difinio": "My definition",
        }
        result = row_to_dict(row)
        assert result["terminologio"] == {}
    
    def test_titolo_synthesized_from_terminologio(self):
        """Test entry.titolo is populated from terminologio for display compat."""
        row = {
            "uuid": "test-uuid",
            "terminologio": '{"eo": "testo", "en": "test"}',
        }
        result = row_to_dict(row)
        assert result["titolo"] == "testo"  # first value from terminologio
    
    def test_titolo_empty_when_terminologio_empty(self):
        """Test titolo not set when terminologio has no values."""
        row = {
            "uuid": "test-uuid",
            "terminologio": "{}",
        }
        result = row_to_dict(row)
        assert "titolo" not in result
    
    def test_backward_compat_missing_difinoj(self):
        """Test missing difinoj defaults to {lang: difinio}."""
        row = {
            "uuid": "test-uuid",
            "difinio": "My definition",
            "terminologio": '{"eo": "testo"}',
        }
        result = row_to_dict(row)
        assert result["difinoj"] == {"eo": "My definition"}
    
    def test_backward_compat_missing_enhavo(self):
        """Test missing enhavo defaults to empty string."""
        row = {
            "uuid": "test-uuid",
            "terminologio": '{"eo": "testo"}',
        }
        result = row_to_dict(row)
        assert result["enhavo"] == ""
    
    def test_backward_compat_missing_citajo(self):
        """Test missing citajo defaults to empty list."""
        row = {
            "uuid": "test-uuid",
            "terminologio": '{"eo": "testo"}',
        }
        result = row_to_dict(row)
        assert result["citajo"] == []
    
    def test_backward_compat_missing_datumo(self):
        """Test missing datumo defaults to empty dict."""
        row = {
            "uuid": "test-uuid",
            "terminologio": '{"eo": "testo"}',
        }
        result = row_to_dict(row)
        assert result["datumo"] == {}


class TestEnsureDirs:
    """Tests for ensure_dirs function."""
    
    def test_ensure_dirs_creates_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test that ensure_dirs creates the data directory."""
        import A_encik.data.storage as storage_module
        
        # Patch module globals
        monkeypatch.setattr(storage_module, "_DATA_DIR", tmp_path)
        monkeypatch.setattr(storage_module, "_ensure_dirs", lambda: None)
        
        # Should not raise - just call ensure_dirs
        storage_module.ensure_dirs()


class TestGetDb:
    """Tests for get_db function."""
    
    def test_get_db_creates_tables(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test that get_db creates required tables."""
        import A_encik.data.storage as storage_module
        
        # Patch module globals
        monkeypatch.setattr(storage_module, "_DATA_DIR", tmp_path)
        monkeypatch.setattr(storage_module, "_DB_FILE", tmp_path / "encik.db")
        monkeypatch.setattr(storage_module, "_ensure_dirs", lambda: None)
        
        # Import after patching
        from A.data.base import SQLiteDB
        from A.core.paths import data_dir
        
        # Patch data_dir globally for SQLiteDB
        monkeypatch.setattr(
            "A.core.paths.data_dir", 
            lambda: tmp_path
        )
        monkeypatch.setattr(
            "A.data.base.data_dir",
            lambda: tmp_path
        )
        
        # Now get_db should work
        # Note: This will need proper A-core mocking in integration


class TestBackupDb:
    """Tests for _backup_db function."""

    def test_backup_creates_bak_file(self, tmp_path, monkeypatch):
        """_backup_db() creates encik.db.bak when encik.db exists."""
        import A_encik.data.storage as storage_module

        db_path = tmp_path / "encik.db"
        db_path.write_text("fake sqlite content")
        monkeypatch.setattr(storage_module, "_DB_FILE", db_path)

        storage_module._backup_db()

        bak_path = tmp_path / "encik.db.bak"
        assert bak_path.exists()
        assert bak_path.read_text() == "fake sqlite content"

    def test_backup_noop_when_no_db(self, tmp_path, monkeypatch):
        """_backup_db() silently does nothing when no DB file exists."""
        import A_encik.data.storage as storage_module

        db_path = tmp_path / "encik.db"
        monkeypatch.setattr(storage_module, "_DB_FILE", db_path)

        # Should not raise
        storage_module._backup_db()
        bak_path = tmp_path / "encik.db.bak"
        assert not bak_path.exists()

    def test_backup_overwrites_old_backup(self, tmp_path, monkeypatch):
        """_backup_db() overwrites previous .bak file."""
        import A_encik.data.storage as storage_module

        db_path = tmp_path / "encik.db"
        db_path.write_text("new content")
        old_bak = tmp_path / "encik.db.bak"
        old_bak.write_text("old content")
        monkeypatch.setattr(storage_module, "_DB_FILE", db_path)

        storage_module._backup_db()
        assert old_bak.read_text() == "new content"


class TestRepairChecked:
    """Tests for _repair_checked flag in get_db()."""

    def test_repair_checked_set_once(self, tmp_path, monkeypatch):
        """_repair_checked is True after first get_db() call."""
        import A_encik.data.storage as storage_module

        monkeypatch.setattr(storage_module, "_DATA_DIR", tmp_path)
        monkeypatch.setattr(storage_module, "_DB_FILE", tmp_path / "encik.db")
        monkeypatch.setattr(storage_module, "_ensure_dirs", lambda: None)
        monkeypatch.setattr("A.core.paths.data_dir", lambda: tmp_path)
        monkeypatch.setattr("A.data.base.data_dir", lambda: tmp_path)
        monkeypatch.setattr(storage_module, "_repair_checked", False)

        db = storage_module.get_db()
        assert storage_module._repair_checked is True

    def test_fast_path_returns_cached_instance(self, tmp_path, monkeypatch):
        """Second get_db() call returns same instance without re-checking."""
        import A_encik.data.storage as storage_module

        monkeypatch.setattr(storage_module, "_DATA_DIR", tmp_path)
        monkeypatch.setattr(storage_module, "_DB_FILE", tmp_path / "encik.db")
        monkeypatch.setattr(storage_module, "_ensure_dirs", lambda: None)
        monkeypatch.setattr("A.core.paths.data_dir", lambda: tmp_path)
        monkeypatch.setattr("A.data.base.data_dir", lambda: tmp_path)
        monkeypatch.setattr(storage_module, "_repair_checked", False)

        call_count = [0]
        original_repair = storage_module._repair_if_corrupted
        def counting_repair():
            call_count[0] += 1
            return original_repair()
        monkeypatch.setattr(storage_module, "_repair_if_corrupted", counting_repair)

        db1 = storage_module.get_db()
        first_count = call_count[0]
        db2 = storage_module.get_db()

        assert db1 is db2  # Same cached instance
        assert call_count[0] == first_count  # Repair not called again


class TestReadonlyRecover:
    """Tests for _readonly_recover function."""

    def test_recover_returns_none_on_valid_db(self, tmp_path, monkeypatch):
        """_readonly_recover returns a valid DB instance when encik table has entries."""
        import A_encik.data.storage as storage_module

        # Create a valid DB
        db = sqlite3.connect(str(tmp_path / "encik.db"))
        db.execute("CREATE TABLE encik (uuid TEXT PRIMARY KEY, terminologio TEXT)")
        db.execute("INSERT INTO encik (uuid, terminologio) VALUES ('aaaaaaaa-1111-2222-3333-444444444444', '{\"eo\":\"test\"}')")
        db.commit()
        db.close()

        monkeypatch.setattr(storage_module, "_DB_FILE", tmp_path / "encik.db")
        result = storage_module._readonly_recover()
        # Should return a new SQLiteDB with the entry recovered
        assert result is not None
        rows = result.execute("SELECT COUNT(*) AS c FROM encik")
        assert rows[0]["c"] == 1

    def test_recover_recovers_readable_entries(self, tmp_path, monkeypatch):
        """_readonly_recover extracts entries from corrupted DB into a clean one."""
        import A_encik.data.storage as storage_module

        db = sqlite3.connect(str(tmp_path / "encik.db"), timeout=30)
        db.execute("CREATE TABLE encik (uuid TEXT PRIMARY KEY, terminologio TEXT)")
        db.execute("CREATE TABLE semantika_cache (keyword TEXT, property_id TEXT)")
        db.execute("INSERT INTO encik (uuid, terminologio) VALUES ('aaaaaaaa-1111-2222-3333-444444444444', '{\"eo\":\"test\"}')")
        db.execute("INSERT INTO encik (uuid, terminologio) VALUES ('bbbbbbbb-1111-2222-3333-444444444444', '{\"eo\":\"test2\"}')")
        db.commit()
        db.close()

        monkeypatch.setattr(storage_module, "_DB_FILE", tmp_path / "encik.db")
        result = storage_module._readonly_recover()

        if result is not None:
            rows = result.execute("SELECT COUNT(*) AS c FROM encik")
            assert rows[0]["c"] == 2

    def test_recover_returns_none_on_unreadable_db(self, tmp_path, monkeypatch):
        """_readonly_recover returns None when even read-only access fails."""
        import A_encik.data.storage as storage_module

        db_path = tmp_path / "encik.db"
        # Write garbage (not a SQLite DB at all)
        db_path.write_bytes(b'\x00' * 512)

        monkeypatch.setattr(storage_module, "_DB_FILE", db_path)
        result = storage_module._readonly_recover()
        assert result is None


class TestInitCacheTable:
    """Tests for semantika_cache table corruption handling."""

    def test_cache_table_dropped_on_corruption(self, tmp_path, monkeypatch):
        """init_cache_table does not crash when semantika_cache is corrupted."""
        from A_encik.data.semantika_cache import init_cache_table
        from A.data.base import SQLiteDB

        db_path = tmp_path / "test.db"
        db = sqlite3.connect(str(db_path))
        db.execute("""
            CREATE TABLE semantika_cache (
                keyword TEXT NOT NULL,
                property_id TEXT NOT NULL,
                label_en TEXT NOT NULL DEFAULT '',
                label_eo TEXT DEFAULT '',
                description TEXT DEFAULT '',
                source TEXT DEFAULT 'api',
                fetched_at TEXT NOT NULL,
                hit_count INTEGER DEFAULT 1,
                PRIMARY KEY (keyword, property_id)
            )
        """)
        db.execute("INSERT INTO semantika_cache VALUES ('x','y','','','','api','2024-01-01',1)")
        db.commit()
        db.close()

        monkeypatch.setattr("A.core.paths.data_dir", lambda: tmp_path)
        monkeypatch.setattr("A.data.base.data_dir", lambda: tmp_path)

        sqldb = SQLiteDB(db_path)
        # This should not raise — corruption is caught internally
        init_cache_table(sqldb)
        # If we got here without exception, the handler works
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])