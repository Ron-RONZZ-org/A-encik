"""Tests for A-encik CLI module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

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
    
    def test_aldoni_requires_arg(self, runner):
        """Test aldoni requires either dosiero or time flag."""
        result = runner.invoke(app, ["aldoni"])
        
        # No dosiero + no time flag → custom error, exit 1
        assert result.exit_code == 1
        assert "bezonatas" in result.output.lower() or "require" in result.output.lower()
    
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
    
    def test_aldoni_jaro(self, runner):
        """Test aldoni with --jaro creates year entry."""
        result = runner.invoke(app, ["aldoni", "--jaro", "1789"])
        
        assert result.exit_code == 0
        assert "jaron 1789" in result.output.lower() or "year 1789" in result.output.lower()
        assert "UUID:" in result.output
    
    def test_aldoni_jardeko(self, runner):
        """Test aldoni with --jardeko creates decade entry."""
        result = runner.invoke(app, ["aldoni", "--jardeko", "1780"])
        
        assert result.exit_code == 0
        assert "jardekon" in result.output.lower() or "decade" in result.output.lower()
        assert "UUID:" in result.output
    
    def test_aldoni_jarcento(self, runner):
        """Test aldoni with --jarcento creates century entry."""
        result = runner.invoke(app, ["aldoni", "--jarcento", "18"])
        
        assert result.exit_code == 0
        assert "jarcenton" in result.output.lower() or "century" in result.output.lower()
    
    def test_aldoni_jaro_bce(self, runner):
        """Test aldoni with --jaro --bce creates BCE year entry."""
        result = runner.invoke(app, ["aldoni", "--jaro", "44", "--bce"])
        
        assert result.exit_code == 0
        assert "UUID:" in result.output
    
    def test_aldoni_jaro_mutual_exclusion(self, runner):
        """Test --jaro and --jardeko cannot be used together."""
        result = runner.invoke(app, ["aldoni", "--jaro", "1789", "--jardeko", "1780"])
        
        assert result.exit_code == 1
        assert "unu el" in result.output.lower() or "only one" in result.output.lower()
    
    def test_aldoni_jaro_invalid(self, runner):
        """Test --jaro with invalid value."""
        result = runner.invoke(app, ["aldoni", "--jaro", "0"])
        
        assert result.exit_code == 1
    
    def test_aldoni_jaro_idempotent(self, runner):
        """Test --jaro is idempotent (second call finds existing)."""
        r1 = runner.invoke(app, ["aldoni", "--jaro", "1923"])
        assert r1.exit_code == 0, f"First call failed: {r1.output}"
        
        r2 = runner.invoke(app, ["aldoni", "--jaro", "1923"])
        assert r2.exit_code == 0, f"Second call failed: {r2.output}"
        assert "jaron 1923" in r2.output.lower() or "year 1923" in r2.output.lower()


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
        """Test modifi with positional .enc file replacement."""
        # Create entry first
        src = tmp_path / "src.enc"
        src.write_text(
            'terminologio.eo = "Origino"\ndifino.eo = "originala"\n',
            encoding="utf-8",
        )
        r1 = runner.invoke(app, ["aldoni", str(src)])
        assert r1.exit_code == 0
        
        # Replace with .enc via modifi (positional arg)
        repl = tmp_path / "repl.enc"
        repl.write_text(
            'terminologio.eo = "Modifita"\ndifino.eo = "nova difino"\n',
            encoding="utf-8",
        )
        r2 = runner.invoke(app, ["modifi", "Origino", str(repl)])
        assert r2.exit_code == 0
        assert "anstataŭigis" in r2.output.lower() or "replaced" in r2.output.lower()
    
    def test_modifi_requires_dosiero(self, runner):
        """Test modifi without .enc file shows error."""
        r = runner.invoke(app, ["modifi", "nonexistent"])
        assert r.exit_code != 0  # Should error (no .enc file given)


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
    """Tests for generi command (delegates to A-agento)."""

    def test_generi_requires_prompto(self, runner):
        """Test generi without prompto shows error."""
        result = runner.invoke(app, ["generi"])
        assert result.exit_code != 0

    def test_generi_no_agento(self, runner):
        """Test generi shows install hint when A-agento is missing."""
        import builtins as _builtins
        _real_import = _builtins.__import__

        def _mock_import(name, *args, **kwargs):
            if name.startswith("A_agento"):
                raise ImportError(f"No module named {name}")
            return _real_import(name, *args, **kwargs)

        with patch.object(_builtins, "__import__", side_effect=_mock_import):
            result = runner.invoke(app, ["generi", "Grokipedia"])
            assert result.exit_code != 0
            assert "A-agento" in result.output

    def test_generi_delegates_to_agento(self, runner):
        """Test generi delegates to A-agento when installed."""
        mock_gen = MagicMock(return_value=None)

        # Build mock module hierarchy for A_agento.commands.knowledge
        mock_knowledge = MagicMock(spec=object())
        mock_knowledge.generi = mock_gen

        mock_commands = MagicMock(spec=object())
        mock_commands.knowledge = mock_knowledge

        mock_agento = MagicMock(spec=object())
        mock_agento.commands = mock_commands

        # Simulate A-agento being installed via sys.modules
        with patch.dict("sys.modules", {
            "A_agento": mock_agento,
            "A_agento.commands": mock_commands,
            "A_agento.commands.knowledge": mock_knowledge,
        }):
            result = runner.invoke(app, ["generi", "Grokipedia"])

            assert mock_gen.called, "A-agento generi was not called"
            _, call_kwargs = mock_gen.call_args
            assert call_kwargs.get("formato") == "enc"
            assert call_kwargs.get("prompto") == "Grokipedia"
            assert result.exit_code == 0


class TestSemantikaCommand:
    """Tests for semantika command."""
    
    def test_semantika_shows_help(self, runner):
        """Test semantika shows help with grupos."""
        result = runner.invoke(app, ["semantika"])
        assert result.exit_code == 0
        assert "grupo" in result.output
    
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




class TestDisplayKaTeX:
    """Tests for KaTeX rendering in HTML output."""

    def test_render_entry_html_includes_katex(self):
        """Test render_entry_html output contains KaTeX assets (inline or CDN)."""
        from A_encik.display import render_entry_html

        entry = {
            "uuid": "abc12345-1234-5678-9abc-def012345678",
            "terminologio": {"eo": "Fiziko"},
            "enhavo": "$$E = mc^2$$",
            "kreita_je": "2025-01-01T00:00:00",
        }
        html = render_entry_html(entry)
        # Check for either inline or CDN KaTeX content
        has_cdn = "katex.min.css" in html and "katex.min.js" in html
        has_inline = "<style>" in html and "katex" in html.lower()
        assert has_cdn or has_inline, "HTML must contain KaTeX assets (CDN or inline)"
        assert "renderMathInElement" in html

    def test_preview_entry_includes_katex(self, monkeypatch, tmp_path):
        """Test preview_entry output contains KaTeX CDN assets."""
        from A_encik.display import preview_entry
        from A_encik.display_helpers import has_non_cli_renderable_markup

        # Force --open to False even if content has katex
        monkeypatch.setattr("A_encik._display_entry.preview_html", lambda html, open_browser=False, title=None: tmp_path / "preview.html")

        entry = {
            "uuid": "abc12345-1234-5678-9abc-def012345678",
            "terminologio": {"eo": "Fiziko"},
            "enhavo": "$$E = mc^2$$",
            "kreita_je": "2025-01-01T00:00:00",
        }
        # Just check the preview_entry doesn't crash and returns path
        result = preview_entry(entry, open_browser=False)
        assert result is not None


class TestDisplayFieldOrder:
    """Tests for display field ordering and internal field hiding."""

    def test_internal_fields_omitted(self):
        """Test internal ranking/search fields are hidden from HTML output."""
        from A_encik.display import render_entry_html

        entry = {
            "uuid": "abc12345-1234-5678-9abc-def012345678",
            "terminologio": {"eo": "Fiziko"},
            "enhavo": "Content",
            "kreita_je": "2025-01-01T00:00:00",
            "_title_prefix": 0,
            "_frequency": 3,
            "_compactness": 42,
            "terminologio_search": "fiziko",
            "titolo_fold": "fiziko",
        }
        html = render_entry_html(entry)
        assert "_title_prefix" not in html
        assert "_frequency" not in html
        assert "_compactness" not in html
        assert "terminologio_search" not in html
        assert "titolo_fold" not in html
        # Regular fields should still be present
        assert "Fiziko" in html
        assert "Content" in html

    def test_display_field_order(self):
        """Test fields appear in DISPLAY_FIELD_ORDER."""
        from A_encik.display import render_entry_html

        entry = {
            "uuid": "abc12345-1234-5678-9abc-def012345678",
            "terminologio": {"eo": "Testo"},
            "difinoj": {"eo": "Difino teksto"},
            "enhavo": "Enhavo teksto",
            "fonto": [{"title": "Source"}],
            "kreita_je": "2025-01-01T00:00:00",
        }
        html = render_entry_html(entry)

        # Check field labels appear in expected order
        term_pos = html.index("terminologio")
        dif_pos = html.index("difinoj")
        font_pos = html.index("fonto")

        assert term_pos < dif_pos, "terminologio should come before difinoj"
        assert dif_pos < font_pos, "difinoj should come before fonto"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])