"""Unit tests for A_encik.enc_format._parser — parse_enc_file."""

from __future__ import annotations

from pathlib import Path

import pytest

from A_encik.enc_format import parse_enc_file, validate_enc_entry


def _write_enc(path: Path, content: str) -> None:
    """Write an .enc file for testing."""
    path.write_text(content, encoding="utf-8")


class TestParseEncFile:
    """Tests for parse_enc_file function."""

    def test_minimal_valid(self, tmp_path: Path) -> None:
        """A valid .enc with terminologio and difino parses."""
        p = tmp_path / "min.enc"
        _write_enc(p, 'terminologio.eo = "testo"\ndifino.eo = "difino"\n')
        result = parse_enc_file(p)
        assert result["terminologio"] == {"eo": "testo"}
        assert result["difinoj"] == {"eo": "difino"}

    def test_terminologio_table_syntax(self, tmp_path: Path) -> None:
        """Inline table syntax for terminologio."""
        p = tmp_path / "table.enc"
        _write_enc(p, 'terminologio = {eo = "testo", en = "test"}\n')
        result = parse_enc_file(p)
        assert result["terminologio"]["eo"] == "testo"
        assert result["terminologio"]["en"] == "test"

    def test_terminologio_only_is_valid(self, tmp_path: Path) -> None:
        """File with only terminologio (no difino) is valid — parser allows either."""
        p = tmp_path / "term_only.enc"
        _write_enc(p, 'terminologio.eo = "only terminologio"\n')
        result = parse_enc_file(p)
        assert result["terminologio"] == {"eo": "only terminologio"}

    def test_difino_only_is_valid(self, tmp_path: Path) -> None:
        """File with only difino (no terminologio) is valid — parser allows either."""
        p = tmp_path / "dif_only.enc"
        _write_enc(p, 'difino.eo = "only difino"\n')
        result = parse_enc_file(p)
        assert result["difinoj"] == {"eo": "only difino"}

    def test_neither_terminologio_nor_difino_raises(self, tmp_path: Path) -> None:
        """File with neither terminologio nor difino raises ValueError."""
        p = tmp_path / "empty.enc"
        _write_enc(p, 'noto = "just a note"\n')
        with pytest.raises(ValueError, match="Nevalida .enc"):
            parse_enc_file(p)

    def test_unknown_key_raises(self, tmp_path: Path) -> None:
        """Unknown top-level key raises ValueError."""
        p = tmp_path / "bad3.enc"
        _write_enc(
            p,
            'terminologio.eo = "testo"\n'
            'difino.eo = "difino"\n'
            'nekonata = "valoro"\n',
        )
        with pytest.raises(ValueError, match="Nekonata kampo"):
            parse_enc_file(p)

    def test_title_from_comment(self, tmp_path: Path) -> None:
        """First # comment used as terminologio when it's missing."""
        p = tmp_path / "comment.enc"
        _write_enc(p, '# Title from comment\ndifino.eo = "difino"\n')
        result = parse_enc_file(p)
        assert result["terminologio"]["eo"] == "Title from comment"

    def test_legacy_difinio_field(self, tmp_path: Path) -> None:
        """Legacy difinio field is converted to difinoj.eo."""
        p = tmp_path / "legacy.enc"
        _write_enc(p, 'terminologio.eo = "testo"\ndifinio = "difino"\n')
        result = parse_enc_file(p)
        assert result["difinoj"]["eo"] == "difino"

    def test_legacy_difino_field(self, tmp_path: Path) -> None:
        """Legacy difino (singular) field is converted."""
        p = tmp_path / "legacy2.enc"
        _write_enc(p, 'terminologio.eo = "testo"\ndifino = "difino"\n')
        result = parse_enc_file(p)
        assert result["difinoj"]["eo"] == "difino"

    def test_superklaso_list(self, tmp_path: Path) -> None:
        """superklaso is parsed as a list of UUIDs."""
        p = tmp_path / "super.enc"
        _write_enc(
            p,
            'terminologio.eo = "testo"\n'
            'difino.eo = "difino"\n'
            'superklaso = ["abc123", "def456"]\n',
        )
        result = parse_enc_file(p)
        assert "superklaso" in result
        assert "abc123" in result["superklaso"]

    def test_ligilo_flat_list(self, tmp_path: Path) -> None:
        """Flat ligilo list is normalized."""
        p = tmp_path / "ligilo.enc"
        _write_enc(
            p,
            'terminologio.eo = "testo"\n'
            'difino.eo = "difino"\n'
            'ligilo = ["abc123", "def456"]\n',
        )
        result = parse_enc_file(p)
        assert "ligilo" in result

    def test_fonto_inline_table(self, tmp_path: Path) -> None:
        """fonto entries are parsed."""
        p = tmp_path / "fonto.enc"
        _write_enc(
            p,
            'terminologio.eo = "testo"\n'
            'difino.eo = "difino"\n'
            'fonto = [{titolo="Book", autoro="Author", jaro=2020}]\n',
        )
        result = parse_enc_file(p)
        assert "fonto" in result
        assert result["fonto"][0]["titolo"] == "Book"

    def test_citajo_inline_table(self, tmp_path: Path) -> None:
        """citajo entries are parsed."""
        p = tmp_path / "citajo.enc"
        _write_enc(
            p,
            'terminologio.eo = "testo"\n'
            'difino.eo = "difino"\n'
            'citajo = [{teksto="Quote", autoro="Author"}]\n',
        )
        result = parse_enc_file(p)
        assert "citajo" in result
        assert result["citajo"][0]["teksto"] == "Quote"

    def test_datumo_block(self, tmp_path: Path) -> None:
        """datumo entries are parsed."""
        p = tmp_path / "datumo.enc"
        _write_enc(
            p,
            'terminologio.eo = "testo"\n'
            'difino.eo = "difino"\n'
            'datumo.formulo = "H2O"\n',
        )
        result = parse_enc_file(p)
        assert "datumo" in result


class TestValidateEncEntry:
    """Tests for validate_enc_entry function."""

    def test_valid_entry_returns_empty(self) -> None:
        """A valid entry produces no errors."""
        entry = {"terminologio": {"eo": "test"}, "difinoj": {"eo": "def"}}
        errors = validate_enc_entry(entry)
        assert errors == []

    def test_missing_terminologio(self) -> None:
        """Missing terminologio produces error."""
        entry = {"difinoj": {"eo": "def"}}
        errors = validate_enc_entry(entry)
        assert len(errors) > 0
        assert any("terminologio" in e for e in errors)

    def test_invalid_superklaso_uuid(self) -> None:
        """Invalid UUID in superklaso produces error."""
        entry = {
            "terminologio": {"eo": "test"},
            "difinoj": {"eo": "def"},
            "superklaso": ["not-a-uuid"],
        }
        errors = validate_enc_entry(entry)
        assert any("Nevalida UUID" in e for e in errors)

    def test_valid_uuid_in_superklaso(self) -> None:
        """Valid UUID in superklaso passes validation."""
        entry = {
            "terminologio": {"eo": "test"},
            "difinoj": {"eo": "def"},
            "superklaso": ["a1b2c3d4-1234-5678-9abc-def012345678"],
        }
        errors = validate_enc_entry(entry)
        assert errors == []
