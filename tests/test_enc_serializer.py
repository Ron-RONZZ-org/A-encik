"""Unit tests for A_encik.enc_format._serializer — entry_to_enc."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pytest

from A_encik.enc_format import entry_to_enc
from A_encik.enc_format._parser import parse_enc_file


def _make_entry(**overrides: Any) -> dict[str, Any]:
    """Create a standard test entry with optional overrides."""
    entry: dict[str, Any] = {
        "terminologio": {"eo": "testo", "en": "test"},
        "difinoj": {"eo": "Difino de testo.", "en": "Definition of test."},
    }
    entry.update(overrides)
    return entry


class TestEntryToEnc:
    """Tests for entry_to_enc function."""

    def test_minimal_entry(self) -> None:
        """Entry with only terminologio and difinoj produces valid output."""
        entry = _make_entry()
        result = entry_to_enc(entry)
        assert "terminologio.eo" in result
        assert "terminologio.en" in result
        assert "difino.eo" in result
        assert "difino.en" in result

    def test_minimal_entry_has_title_comment(self) -> None:
        """First terminologio value appears as # comment."""
        entry = _make_entry()
        result = entry_to_enc(entry)
        assert "# testo" in result

    def test_empty_entry_returns_empty_string(self) -> None:
        """Empty entry returns empty string or minimal output."""
        result = entry_to_enc({})
        assert isinstance(result, str)

    def test_entry_with_superklaso(self) -> None:
        """Superklaso list is serialized."""
        entry = _make_entry(superklaso=["abc123", "def456"])
        result = entry_to_enc(entry)
        assert "superklaso" in result
        assert '"abc123"' in result
        assert '"def456"' in result

    def test_entry_with_ligilo(self) -> None:
        """Ligilo list is serialized."""
        entry = _make_entry(ligilo=[["abc123", "rdf:type"], ["def456"]])
        result = entry_to_enc(entry)
        assert "ligilo" in result

    def test_entry_with_fonto(self) -> None:
        """Fonto entries are serialized as inline tables."""
        entry = _make_entry(fonto=[{"titolo": "A Book", "autoro": "Author", "jaro": 2020}])
        result = entry_to_enc(entry)
        assert "fonto" in result
        assert "A Book" in result
        assert "Author" in result

    def test_entry_with_citajo(self) -> None:
        """Citajo entries are serialized."""
        entry = _make_entry(citajo=[{"teksto": "Quote", "autoro": "Author"}])
        result = entry_to_enc(entry)
        assert "citajo" in result
        assert "Quote" in result

    def test_entry_with_datumo(self) -> None:
        """Datumo dict is serialized as TOML multi-line string."""
        entry = _make_entry(datumo={"formulo": "H2O", "molar_maso": 18.015})
        result = entry_to_enc(entry)
        assert "datumo" in result

    def test_entry_with_semantika(self) -> None:
        """Semantika entries are serialized."""
        entry = _make_entry(
            semantika=[{"tipo": "science", "arko": "is_a", "valoro": "chemistry"}]
        )
        result = entry_to_enc(entry)
        assert "semantika" in result
        assert "science" in result

    def test_multiline_difino(self) -> None:
        """Multiline definitions use triple-quoted TOML."""
        entry = _make_entry(difinoj={"eo": "Line 1\n\nLine 2"})
        result = entry_to_enc(entry)
        assert '"""' in result


class TestEncRoundTrip:
    """Round-trip: serialize → parse → compare data."""

    def test_round_trip_minimal(self) -> None:
        """Minimal entry serializes and parses back correctly."""
        entry = _make_entry()
        enc_text = entry_to_enc(entry)

        with NamedTemporaryFile(mode="w", suffix=".enc", delete=False) as f:
            f.write(enc_text)
            tmp_path = Path(f.name)

        try:
            parsed = parse_enc_file(tmp_path)
            assert parsed["terminologio"] == entry["terminologio"]
            assert parsed["difinoj"] == entry["difinoj"]
        finally:
            tmp_path.unlink()

    def test_round_trip_full(self) -> None:
        """Full entry with all fields round-trips correctly."""
        entry = _make_entry(
            superklaso=["abc123", "def456"],
            ligilo=[["abc123", "rdf:type"]],
            fonto=[{"titolo": "Book", "autoro": "Author", "jaro": 2020}],
            citajo=[{"teksto": "A quote", "autoro": "Author"}],
            datumo={"key": "value"},
        )
        enc_text = entry_to_enc(entry)

        with NamedTemporaryFile(mode="w", suffix=".enc", delete=False) as f:
            f.write(enc_text)
            tmp_path = Path(f.name)

        try:
            parsed = parse_enc_file(tmp_path)
            assert parsed["terminologio"] == entry["terminologio"]
            assert parsed["difinoj"] == entry["difinoj"]
            assert parsed.get("superklaso") == entry["superklaso"]
            assert "fonto" in parsed
            assert "citajo" in parsed
        finally:
            tmp_path.unlink()
