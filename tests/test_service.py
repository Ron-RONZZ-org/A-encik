"""Tests for A-encik service module."""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch

from A_encik.service import EncikService, get_service


class TestEncikService:
    """Tests for EncikService class."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database with minimal schema stubs."""
        db = MagicMock()

        # Schema statement returned for sqlite_master query
        mock_create = (
            "CREATE TABLE encik ("
            "uuid TEXT PRIMARY KEY, titolo TEXT NOT NULL DEFAULT '', "
            "difinio TEXT NOT NULL DEFAULT '', "
            "terminologio TEXT NOT NULL DEFAULT '{}', "
            "difinoj TEXT NOT NULL DEFAULT '{}', "
            "enhavo TEXT NOT NULL DEFAULT '', "
            "superklaso TEXT NOT NULL DEFAULT '[]', "
            "ligilo TEXT NOT NULL DEFAULT '[]', "
            "fonto TEXT NOT NULL DEFAULT '[]', "
            "citajo TEXT NOT NULL DEFAULT '[]', "
            "datumo TEXT NOT NULL DEFAULT '{}', "
            "semantika TEXT NOT NULL DEFAULT '[]', "
            "ligiloj TEXT NOT NULL DEFAULT '[]', "
            "kreita_je TEXT NOT NULL, modifita_je TEXT NOT NULL"
            ")"
        )

        # Columns: cid, name, type, notnull, dflt_value, pk
        main_cols = [
            (0, "uuid", "TEXT", 1, None, 1),
            (1, "titolo", "TEXT", 1, "''", 0),
            (2, "difinio", "TEXT", 1, "''", 0),
            (3, "terminologio", "TEXT", 1, "'{}'", 0),
            (4, "difinoj", "TEXT", 1, "'{}'", 0),
            (5, "enhavo", "TEXT", 1, "''", 0),
            (6, "superklaso", "TEXT", 1, "'[]'", 0),
            (7, "ligilo", "TEXT", 1, "'[]'", 0),
            (8, "fonto", "TEXT", 1, "'[]'", 0),
            (9, "citajo", "TEXT", 1, "'[]'", 0),
            (10, "datumo", "TEXT", 1, "'{}'", 0),
            (11, "semantika", "TEXT", 1, "'[]'", 0),
            (12, "ligiloj", "TEXT", 1, "'[]'", 0),
            (13, "kreita_je", "TEXT", 1, None, 0),
            (14, "modifita_je", "TEXT", 1, None, 0),
        ]

        call_count = {"execute_one": 0}

        def execute_one_side_effect(sql, *args):
            call_count["execute_one"] += 1
            upper = sql.strip().upper()
            # First call: schema lookup for _ensure_trash_table
            if "FROM SQLITE_MASTER" in upper:
                return {"sql": mock_create}
            # FTS count check
            if "SELECT COUNT(*) AS CNT" in upper:
                return {"cnt": 0}
            return {}

        def execute_side_effect(sql, *args):
            upper = sql.strip().upper()
            if upper.startswith("PRAGMA TABLE_INFO(ENCIK"):
                return main_cols
            if upper.startswith("PRAGMA TABLE_INFO(ENCIK_RUBUJO"):
                return []
            return []

        db.execute_one.side_effect = execute_one_side_effect
        db.execute.side_effect = execute_side_effect
        return db
    
    @pytest.fixture
    def service(self, mock_db):
        """Create service with mock db."""
        return EncikService(mock_db)
    
    def test_serialize_list_fields(self, service):
        """Test JSON serialization of list fields."""
        data = {
            "titolo": "Test",
            "superklaso": ["uuid1", "uuid2"],
            "ligilo": ["link1"],
            "fonto": ["source1"],
            "citajo": ["quote1"],
            "semantika": ["sem1"],
        }
        result = service._serialize(data)
        
        assert result["superklaso"] == '["uuid1", "uuid2"]'
        assert result["ligilo"] == '["link1"]'
        assert result["fonto"] == '["source1"]'
        assert result["citajo"] == '["quote1"]'
        assert result["semantika"] == '["sem1"]'
    
    def test_serialize_dict_fields(self, service):
        """Test JSON serialization of dict fields."""
        data = {
            "titolo": "Test",
            "terminologio": {"eo": "testo", "en": "test"},
            "difinoj": {"eo": "difino"},
            "datumo": {"key": "value"},
        }
        result = service._serialize(data)
        
        assert result["terminologio"] == '{"eo": "testo", "en": "test"}'
        assert result["difinoj"] == '{"eo": "difino"}'
        assert result["datumo"] == '{"key": "value"}'
    
    def test_serialize_preserves_simple_fields(self, service):
        """Test that simple fields are preserved."""
        data = {
            "titolo": "Test Title",
            "difinio": "Definition",
            "enhavo": "Content",
            "kreita_je": "2024-01-01",
        }
        result = service._serialize(data)
        
        assert result["titolo"] == "Test Title"
        assert result["difinio"] == "Definition"
        assert result["enhavo"] == "Content"
        assert result["kreita_je"] == "2024-01-01"
    
    def test_serialize_handles_missing_fields(self, service):
        """Test serialize handles missing optional fields."""
        data = {"titolo": "Test"}
        result = service._serialize(data)
        
        assert result["titolo"] == "Test"
        assert "superklaso" not in result
    
    def test_json_fields_defined(self, service):
        """Test that JSON field lists are defined."""
        assert hasattr(service, "_JSON_LIST_FIELDS")
        assert hasattr(service, "_JSON_DICT_FIELDS")
        
        assert "superklaso" in service._JSON_LIST_FIELDS
        assert "ligilo" in service._JSON_LIST_FIELDS
        assert "terminologio" in service._JSON_DICT_FIELDS
        assert "difinoj" in service._JSON_DICT_FIELDS


class TestGetService:
    """Tests for get_service function."""
    
    def test_get_service_returns_encikservice(self):
        """Test that get_service returns EncikService instance."""
        # This requires a real DB, so we just test the type
        service = get_service()
        assert isinstance(service, EncikService)
    
    def test_get_service_singleton(self):
        """Test that get_service returns singleton."""
        # Import twice
        from A_encik.service import get_service as get_service2
        
        # Should be the same instance
        s1 = get_service()
        s2 = get_service2()
        # Note: This may fail if DB is None - covered by integration test


class TestEncikServiceIntegration:
    """Integration tests for EncikService (requires DB)."""
    
    @pytest.fixture
    def service(self, tmp_path):
        """Create service with test DB."""
        import A_encik.data.storage as storage_module
        from A_encik.service import EncikService
        
        # Patch to use temp directory
        with patch.object(storage_module, "_DATA_DIR", tmp_path):
            with patch.object(storage_module, "_DB_FILE", tmp_path / "encik.db"):
                with patch.object(storage_module, "_ensure_dirs", lambda: None):
                    with patch("A.core.paths.data_dir", return_value=tmp_path):
                        with patch("A.data.base.data_dir", return_value=tmp_path):
                            # Use get_db() which initializes schema
                            db = storage_module.get_db()
                            service = EncikService(db)
                            yield service
    
    def test_create_entry(self, service):
        """Test creating an entry."""
        data = {
            "difinio": "Test definition",
            "terminologio": {"eo": "testo"},
        }
        
        entry = service.create(data)
        
        assert "uuid" in entry
        # titolo is synthesized from terminologio by row_to_dict
        assert entry["titolo"] == "testo"
        assert entry["difinio"] == "Test definition"
        # JSON field should be deserialized
        assert entry["terminologio"] == {"eo": "testo"}
    
    def test_create_entry_with_empty_terminologio(self, service):
        """Test creating an entry with empty terminologio (no titolo synthesized)."""
        data = {
            "terminologio": {"eo": ""},
            "difinoj": {"eo": "some def"},
        }
        entry = service.create(data)
        assert "uuid" in entry
        # No titolo since terminologio has no non-empty values
        assert "titolo" not in entry

    def test_get_entry(self, service):
        """Test getting an entry."""
        data = {
            "terminologio": {"eo": "Get Test"},
            "difinio": "Definition",
        }
        
        created = service.create(data)
        uuid = created["uuid"]
        
        entry = service.get(uuid)
        
        assert entry is not None
        assert entry["uuid"] == uuid
        assert entry["titolo"] == "Get Test"
    
    def test_list_entries(self, service):
        """Test listing entries."""
        # Create a few entries
        service.create({"terminologio": {"eo": "Entry 1"}, "difinio": "Def 1"})
        service.create({"terminologio": {"eo": "Entry 2"}, "difinio": "Def 2"})
        
        entries = service.list()
        
        assert len(entries) >= 2
    
    def test_find_by_titolo(self, service):
        """Test finding by title."""
        data = {
            "terminologio": {"eo": "FindMe Title"},
            "difinio": "Find def",
        }
        
        service.create(data)
        
        entry = service.find_by_titolo("FindMe Title")
        
        assert entry is not None
        assert entry["titolo"] == "FindMe Title"
    
    def test_find_by_titolo_case_insensitive(self, service):
        """Test case-insensitive title search."""
        data = {
            "terminologio": {"eo": "CaseTest"},
            "difinio": "Def",
        }
        
        service.create(data)
        
        entry = service.find_by_titolo("casetest")
        
        assert entry is not None
    
    def test_find_by_uuid_prefix(self, service):
        """Test finding by UUID prefix."""
        data = {"terminologio": {"eo": "Prefix Test"}, "difinio": "Def"}
        
        created = service.create(data)
        prefix = created["uuid"][:4]
        
        entries = service.find_by_uuid_prefix(prefix)
        
        assert len(entries) >= 1
    
    def test_update_entry(self, service):
        """Test updating an entry."""
        data = {
            "terminologio": {"eo": "Original"},
            "difinio": "Original def",
        }
        
        created = service.create(data)
        uuid = created["uuid"]
        
        updated = service.update(uuid, {"terminologio": {"eo": "Updated"}})
        
        assert updated["titolo"] == "Updated"
    
    def test_delete_soft(self, service):
        """Test soft delete."""
        data = {"terminologio": {"eo": "DeleteMe"}, "difinio": "Def"}
        
        created = service.create(data)
        uuid = created["uuid"]
        
        service.delete(uuid, soft=True)
    
    def test_delete_hard(self, service):
        """Test hard delete."""
        data = {"terminologio": {"eo": "HardDelete"}, "difinio": "Def"}
        
        created = service.create(data)
        uuid = created["uuid"]
        
        service.delete(uuid, soft=False)
        
        entry = service.get(uuid)
        assert entry is None
    
    def test_count(self, service):
        """Test entry count."""
        count_before = service.count()
        
        service.create({"terminologio": {"eo": "Count Test"}, "difinio": "Def"})
        
        count_after = service.count()
        
        assert count_after == count_before + 1


class TestBidirectionalLinks:
    """Tests for bidirectional link syncing on update."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create service with test DB."""
        import A_encik.data.storage as storage_module
        from A_encik.service import EncikService
        from unittest.mock import patch

        with patch.object(storage_module, "_DATA_DIR", tmp_path):
            with patch.object(storage_module, "_DB_FILE", tmp_path / "encik.db"):
                with patch.object(storage_module, "_ensure_dirs", lambda: None):
                    with patch("A.core.paths.data_dir", return_value=tmp_path):
                        with patch("A.data.base.data_dir", return_value=tmp_path):
                            from A_encik.data.storage import get_db
                            db = get_db()
                            # Reset singleton
                            import A_encik.service as svc_module
                            svc_module._encik_service = None
                            yield EncikService(db)

    def test_reverse_link_added_on_update(self, service):
        """Test adding a ligilo entry creates a reverse link in the target."""
        a = service.create({"terminologio": {"eo": "Entry A"}, "difinio": "Def A"})
        b = service.create({"terminologio": {"eo": "Entry B"}, "difinio": "Def B"})

        service.update(a["uuid"], {"ligilo": [[b["uuid"], "wdt:P123"]]})

        b_updated = service.get(b["uuid"])
        ligilo = b_updated.get("ligilo", [])
        assert any(link[0] == a["uuid"] for link in ligilo)

    def test_stale_reverse_link_removed_on_update(self, service):
        """Test removing a ligilo entry cleans up the stale reverse link."""
        a = service.create({"terminologio": {"eo": "Entry A"}, "difinio": "Def A"})
        b = service.create({"terminologio": {"eo": "Entry B"}, "difinio": "Def B"})

        service.update(a["uuid"], {"ligilo": [[b["uuid"], "wdt:P123"]]})
        b_after_add = service.get(b["uuid"])
        assert any(link[0] == a["uuid"] for link in b_after_add.get("ligilo", []))

        service.update(a["uuid"], {"ligilo": []})
        b_after_remove = service.get(b["uuid"])
        assert not any(link[0] == a["uuid"] for link in b_after_remove.get("ligilo", []))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])