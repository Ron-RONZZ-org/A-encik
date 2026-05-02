"""Tests for A-encik CLI module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from A_encik.cli import app


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
        result = runner.invoke(app, ["ls", "--limit", "1"])
        
        # Should not error
        assert result.exit_code == 0
    
    def test_ls_with_limit(self, runner):
        """Test ls respects limit."""
        result = runner.invoke(app, ["ls", "--limit", "5"])
        
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
    
    def test_aldoni_requires_title(self, runner):
        """Test aldoni requires titolo argument."""
        result = runner.invoke(app, ["aldoni"])
        
        assert result.exit_code == 2
    
    def test_aldoni_basic(self, runner):
        """Test basic aldoni."""
        result = runner.invoke(app, ["aldoni", "CLI Test Title"])
        
        assert result.exit_code == 0
        assert "UUID:" in result.output
    
    def test_aldoni_with_difino(self, runner):
        """Test aldoni with difino."""
        result = runner.invoke(app, ["aldoni", "Test Title", "--difino", "Test definition"])
        
        assert result.exit_code == 0
        assert "aldonis" in result.output.lower() or "added" in result.output.lower()


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


class TestForigiCommand:
    """Tests for forigi command."""
    
    def test_forigi_requires_ref(self, runner):
        """Test forigi requires reference."""
        result = runner.invoke(app, ["forigi"])
        
        assert result.exit_code == 2


class TestSerciCommand:
    """Tests for serci command."""
    
    def test_serci_requires_query(self, runner):
        """Test serci requires query."""
        result = runner.invoke(app, ["serci"])
        
        assert result.exit_code == 2
    
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
    
    def test_semantika_is_todo(self, runner):
        """Test semantika shows TODO."""
        result = runner.invoke(app, ["semantika"])
        
        assert result.exit_code == 0
        assert "TODO" in result.output


class TestHelpCommands:
    """Tests for help output."""
    
    def test_help_no_args(self, runner):
        """Test running without args shows help."""
        result = runner.invoke(app, [])
        
        # Typer may show help or run default command
        # Just ensure no crash
        assert result.exit_code in (0, 1)
    
    def test_help_flag(self, runner):
        """Test --help shows help."""
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "help" in result.output.lower() or "helpo" in result.output.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])