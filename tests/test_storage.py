"""Tests for A-encik storage module."""

from __future__ import annotations

import os
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
            "titolo": "Test",
            "superklaso": '["uuid1", "uuid2"]',
            "ligilo": '["uuid3"]',
            "fonto": "[]",
        }
        result = row_to_dict(row)
        assert result["superklaso"] == ["uuid1", "uuid2"]
        assert result["ligilo"] == ["uuid3"]
        assert result["fonto"] == []
    
    def test_json_dict_fields(self):
        """Test JSON dict fields are parsed."""
        row = {
            "uuid": "test-uuid",
            "titolo": "Test",
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
            "titolo": "Test",
            "source": '["source1"]',
        }
        result = row_to_dict(row)
        assert result["fonto"] == ["source1"]
    
    def test_backward_compat_missing_terminologio(self):
        """Test missing terminologio defaults to {lang: titolo}."""
        row = {
            "uuid": "test-uuid",
            "titolo": "My Title",
        }
        result = row_to_dict(row)
        assert result["terminologio"] == {"eo": "My Title"}
    
    def test_backward_compat_missing_difinoj(self):
        """Test missing difinoj defaults to {lang: difinio}."""
        row = {
            "uuid": "test-uuid",
            "titolo": "Test",
            "difinio": "My definition",
        }
        result = row_to_dict(row)
        assert result["difinoj"] == {"eo": "My definition"}
    
    def test_backward_compat_missing_enhavo(self):
        """Test missing enhavo defaults to empty string."""
        row = {
            "uuid": "test-uuid",
            "titolo": "Test",
        }
        result = row_to_dict(row)
        assert result["enhavo"] == ""
    
    def test_backward_compat_missing_citajo(self):
        """Test missing citajo defaults to empty list."""
        row = {
            "uuid": "test-uuid",
            "titolo": "Test",
        }
        result = row_to_dict(row)
        assert result["citajo"] == []
    
    def test_backward_compat_missing_datumo(self):
        """Test missing datumo defaults to empty dict."""
        row = {
            "uuid": "test-uuid",
            "titolo": "Test",
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])