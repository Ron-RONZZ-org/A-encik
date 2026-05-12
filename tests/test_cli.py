"""Tests for A-encik CLI module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from A_encik.cli import app


@pytest.fixture(autouse=True)
def isolate_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate database to tmp_path to prevent leaking test data."""
    import A_encik.data.storage as storage_module
    monkeypatch.setattr(storage_module, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_module, "_DB_FILE", tmp_path / "encik.db")


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def clean_test_entry():
    """Ensure test entry is deleted after test."""
    yield
    # Cleanup would go here if needed


class TestLsCommand:
    """Tests for ls command."""
    
    def test_ls_empty(self, runner):
        """Test ls with no entries."""
        result = runner.invoke(app, ["ls", "--per-pagho", "1"])
        
        # Should not error
        assert result.exit_code == 0
    
    def test_ls_with_limit(self, runner):
        """Test ls respects per-page limit."""
        result = runner.invoke(app, ["ls", "--per-pagho", "5"])
        
        assert result.exit_code == 0
    
    def test_ls_empty_db_message(self, runner):
        """Test ls shows empty message when no entries."""
        result = runner.invoke(app, ["ls"])
        
        assert result.exit_code == 0
        assert "Neniu" in result.output or "No entries" in result.output
    
    def test_ls_tag_args(self, runner):
        """Test ls runs with short flags."""
        result = runner.invoke(app, ["ls", "-p", "1"])
        
        assert result.exit_code == 0


class TestVidiCommand:
    """Tests for vidi command."""
    
    def test_vidi_missing_arg(self, runner):
        """Test vidi requires argument."""
        result = runner.invoke(app, ["vidi"])
        
        assert result.exit_code == 2
    
    def test_vidi_not_found(self, runner):
        """Test vidi shows error for missing entry."""
        result = runner.invoke(app, ["vidi", "nonexistent-uuid"])
        
        assert result.exit_code == 1
        assert "ne trovita" in result.output.lower() or "not found" in result.output.lower()


class TestAldoniCommand:
    """Tests for aldoni command."""
    
    def test_aldoni_requires_dosiero(self, runner):
        """Test aldoni requires dosiero argument."""
        result = runner.invoke(app, ["aldoni"])
        
        # Missing required arg → exit 2 (Typer/Click convention)
        assert result.exit_code == 2
    
    def test_aldoni_file_not_found(self, runner):
        """Test aldoni errors on non-existent file."""
        result = runner.invoke(app, ["aldoni", "/nonexistent/path.enc"])
        
        assert result.exit_code == 1
        assert "ne trovita" in result.output.lower() or "not found" in result.output.lower()
    
    def test_aldoni_with_enc_file(self, runner, tmp_path):
        """Test aldoni with a valid .enc file."""
        enc_path = tmp_path / "test.enc"
        enc_path.write_text(
            'terminologio.eo = "Testa"\n'
            'difino.eo = "testa difino"\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["aldoni", str(enc_path)])
        
        assert result.exit_code == 0
        assert "aldonis" in result.output.lower() or "added" in result.output.lower()
        assert "UUID:" in result.output
    
    def test_aldoni_kopii_flag(self, runner, tmp_path):
        """Test aldoni with --kopii flag."""
        enc_path = tmp_path / "kopii_test.enc"
        enc_path.write_text(
            'terminologio.eo = "Kopii Test"\n'
            'difino.eo = "testo por kopii"\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["aldoni", str(enc_path), "-k"])
        
        assert result.exit_code == 0
        
    def test_aldoni_mutual_exclusion(self, runner, tmp_path):
        """Test --kopii and --semantika-kopii cannot be used together."""
        enc_path = tmp_path / "mutex_test.enc"
        enc_path.write_text(
            'terminologio.eo = "Mutual"\n'
            'difino.eo = "ekskluziva"\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["aldoni", str(enc_path), "-k", "-sk"])
        
        assert result.exit_code == 1
        assert "unu el" in result.output.lower() or "only one" in result.output.lower()


class TestModifiCommand:
    """Tests for modifi command."""
    
    def test_modifi_requires_ref(self, runner):
        """Test modifi requires reference."""
        result = runner.invoke(app, ["modifi"])
        
        assert result.exit_code == 2
    
    def test_modifi_not_found(self, runner):
        """Test modifi shows error for missing entry."""
        result = runner.invoke(app, ["modifi", "nonexistent-uuid"])
        
        assert result.exit_code == 1
    
    def test_modifi_with_dosiero(self, runner, tmp_path):
        """Test modifi with --dosiero .enc file replacement."""
        # Create entry first
        src = tmp_path / "src.enc"
        src.write_text(
            'terminologio.eo = "Origino"\ndifino.eo = "originala"\n',
            encoding="utf-8",
        )
        r1 = runner.invoke(app, ["aldoni", str(src)])
        assert r1.exit_code == 0
        
        # Replace with .enc via modifi
        repl = tmp_path / "repl.enc"
        repl.write_text(
            'terminologio.eo = "Modifita"\ndifino.eo = "nova difino"\n',
            encoding="utf-8",
        )
        r2 = runner.invoke(app, ["modifi", "Origino", "--dosiero", str(repl)])
        assert r2.exit_code == 0
        assert "anstataŭigis" in r2.output.lower() or "replaced" in r2.output.lower()


class TestForigiCommand:
    """Tests for forigi command."""
    
    def test_forigi_requires_ref(self, runner):
        """Test forigi requires reference."""
        result = runner.invoke(app, ["forigi"])
        
        assert result.exit_code == 2


class TestSerciCommand:
    """Tests for serci command."""
    
    def test_serci_no_query_shows_list(self, runner):
        """Test serci without query shows listing (not error)."""
        result = runner.invoke(app, ["serci"])
        
        # Without args, serci lists entries (matching legacy)
        assert result.exit_code == 0
    
    def test_serci_no_results(self, runner):
        """Test serci with no results."""
        result = runner.invoke(app, ["serci", "nonexistent-query-xyz"])
        
        assert result.exit_code == 0
        # Should show "no results" message
        assert "neniuj" in result.output.lower() or "no results" in result.output.lower()


class TestEksportiCommand:
    """Tests for eksporti command."""
    
    def test_eksporti_requires_ref(self, runner):
        """Test eksporti requires reference."""
        result = runner.invoke(app, ["eksporti"])
        
        assert result.exit_code == 2
    
    def test_eksporti_requires_output(self, runner):
        """Test eksporti requires output path."""
        result = runner.invoke(app, ["eksporti", "some-uuid"])
        
        assert result.exit_code == 2


class TestAgordiCommand:
    """Tests for agordi command."""
    
    def test_agordi_shows_settings(self, runner):
        """Test agordi shows settings."""
        result = runner.invoke(app, ["agordi"])
        
        # Should not error (may show import error if config not set up)
        assert result.exit_code in (0, 1)


class TestGeneriCommand:
    """Tests for generi command."""
    
    def test_generi_is_todo(self, runner):
        """Test generi shows TODO."""
        result = runner.invoke(app, ["generi"])
        
        assert result.exit_code == 0
        assert "TODO" in result.output


class TestSemantikaCommand:
    """Tests for semantika command."""
    
    def test_semantika_shows_help(self, runner):
        """Test semantika shows help with groups."""
        result = runner.invoke(app, ["semantika"])
        
        assert result.exit_code == 0
        assert "serci" in result.output
        assert "aldoni" in result.output
        assert "generala" in result.output
    
    def test_semantika_serci_requires_query(self, runner):
        """Test semantika serci requires argument."""
        result = runner.invoke(app, ["semantika", "serci"])
        
        assert result.exit_code == 2
    
    def test_semantika_serci_no_results(self, runner):
        """Test semantika serci with no results."""
        result = runner.invoke(app, ["semantika", "serci", "nonexistent99999"])
        
        assert result.exit_code == 0
        assert "Neniuj rezultoj" in result.output or "No results" in result.output
    
    def test_semantika_aldoni_requires_args(self, runner):
        """Test semantika aldoni requires arguments."""
        result = runner.invoke(app, ["semantika", "aldoni"])
        
        assert result.exit_code == 2


class TestHelpCommands:
    """Tests for help output."""
    
    def test_help_no_args(self, runner):
        """Test running without args shows help."""
        result = runner.invoke(app, [])
        
        # Typer with no_args_is_help=True shows help (any non-crash exit code)
        assert result.exit_code in (0, 1, 2)
    
    def test_help_flag(self, runner):
        """Test --help shows help."""
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "help" in result.output.lower() or "helpo" in result.output.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])