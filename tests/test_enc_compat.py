"""Unit tests for A_encik.enc_format._compat — legacy compatibility pre-processors."""

from __future__ import annotations

from A_encik.enc_format._compat import (
    escape_latex_style_backslashes,
    expand_multi_locale_assignments,
    extract_enhavo_block,
    fix_inline_table_commas,
    fix_unquoted_uuids,
    normalize_markdown_text,
    normalize_multiline_value_spacing,
)


class TestNormalizeMultilineValueSpacing:
    """Tests for normalize_multiline_value_spacing."""

    def test_no_change_when_already_spaced(self) -> None:
        """Already properly spaced multiline values are unchanged."""
        raw = 'key = """\nvalue\n"""'
        assert normalize_multiline_value_spacing(raw) == raw

    def test_preserves_empty_strings(self) -> None:
        """Empty strings are not affected."""
        raw = 'key = ""'
        assert normalize_multiline_value_spacing(raw) == raw


class TestExpandMultiLocaleAssignments:
    """Tests for expand_multi_locale_assignments."""

    def test_expand_two_locales(self) -> None:
        """Shorthand (eo,en) expands to two lines."""
        raw = 'terminologio.(eo,en) = "Termo"\n'
        result = expand_multi_locale_assignments(raw)
        assert 'terminologio.eo = "Termo"' in result
        assert 'terminologio.en = "Termo"' in result

    def test_expand_three_locales(self) -> None:
        """Shorthand (eo,en,fr) expands to three lines."""
        raw = 'difino.(eo,en,fr) = "Difino"\n'
        result = expand_multi_locale_assignments(raw)
        assert 'difino.eo = "Difino"' in result
        assert 'difino.en = "Difino"' in result
        assert 'difino.fr = "Difino"' in result

    def test_no_change_without_parens(self) -> None:
        """Normal single-locale lines are unchanged."""
        raw = 'terminologio.eo = "Termo"\n'
        assert expand_multi_locale_assignments(raw) == raw

    def test_handles_dotted_prefixes(self) -> None:
        """Works with dotted prefixes like datumo.(eo,en)."""
        raw = 'datumo.(eo,en) = "data"\n'
        result = expand_multi_locale_assignments(raw)
        assert 'datumo.eo = "data"' in result
        assert 'datumo.en = "data"' in result


class TestEscapeLatexStyleBackslashes:
    """Tests for escape_latex_style_backslashes."""

    def test_preserves_toml_quote_escapes(self) -> None:
        """\\" inside string is preserved as valid TOML."""
        raw = 'x = "he said \\"hello\\""\n'
        result = escape_latex_style_backslashes(raw)
        # Should not corrupt the string
        assert '\\"' in result

    def test_empty_string_unchanged(self) -> None:
        """Empty input is unchanged."""
        assert escape_latex_style_backslashes("") == ""


class TestFixInlineTableCommas:
    """Tests for fix_inline_table_commas."""

    def test_adds_missing_comma(self) -> None:
        """{titolo=\"...\" autoro=\"...\"} → {titolo=\"...\", autoro=\"...\"}."""
        raw = '{titolo="Book" autoro="Author"}'
        result = fix_inline_table_commas(raw)
        assert ", " in result

    def test_preserves_existing_commas(self) -> None:
        """Already correct tables are preserved."""
        raw = '{titolo="Book", autoro="Author"}'
        result = fix_inline_table_commas(raw)
        assert result == raw

    def test_no_change_outside_tables(self) -> None:
        """Content outside {} is not affected."""
        raw = 'key = "value"\n'
        assert fix_inline_table_commas(raw) == raw


class TestFixUnquotedUuids:
    """Tests for fix_unquoted_uuids."""

    def test_quotes_bare_uuid(self) -> None:
        """[abc123] → [\"abc123\"]."""
        raw = "ligilo = [abc123]"
        result = fix_unquoted_uuids(raw)
        assert '"abc123"' in result

    def test_quotes_multiple_uuids(self) -> None:
        """[abc, def] → [\"abc\", \"def\"]."""
        raw = "ligilo = [abc, def]"
        result = fix_unquoted_uuids(raw)
        assert '"abc"' in result
        assert '"def"' in result

    def test_preserves_quoted_strings(self) -> None:
        """Already quoted strings are unchanged."""
        raw = 'ligilo = ["abc", "def"]'
        assert fix_unquoted_uuids(raw) == raw

    def test_preserves_numbers(self) -> None:
        """Numbers are left unquoted."""
        raw = "x = [1, 2, 3]"
        result = fix_unquoted_uuids(raw)
        assert result == raw

    def test_preserves_booleans(self) -> None:
        """true/false are left unquoted."""
        raw = "x = [true, false]"
        result = fix_unquoted_uuids(raw)
        assert result == raw

    def test_no_change_outside_arrays(self) -> None:
        """Content outside [] is not affected."""
        raw = 'key = "value"\n'
        assert fix_unquoted_uuids(raw) == raw


class TestExtractEnhavoBlock:
    """Tests for extract_enhavo_block."""

    def test_extracts_bare_triple_quoted_block(self) -> None:
        """Bare \"\"\"...\"\"\" block is extracted as enhavo."""
        raw = 'titolo = "Test"\n"""\nContent here\n"""\n'
        stripped, enhavo = extract_enhavo_block(raw)
        assert "Content here" in enhavo
        assert 'titolo = "Test"' in stripped

    def test_no_block_returns_empty(self) -> None:
        """No bare \"\"\" block returns empty enhavo."""
        raw = 'titolo = "Test"\n'
        stripped, enhavo = extract_enhavo_block(raw)
        assert enhavo == ""
        assert stripped == raw

    def test_ignores_prefixed_multiline(self) -> None:
        """enhavo = \"\"\" block is not extracted (only bare \"\"\")."""
        raw = 'enhavo = """\ncontent\n"""\n'
        stripped, enhavo = extract_enhavo_block(raw)
        assert enhavo == ""


class TestNormalizeMarkdownText:
    """Tests for normalize_markdown_text."""

    def test_fixes_heading_spacing(self) -> None:
        """#Title → # Title."""
        result = normalize_markdown_text("#Title")
        assert result == "# Title"

    def test_preserves_proper_headings(self) -> None:
        """# Title stays # Title."""
        result = normalize_markdown_text("# Title")
        assert result == "# Title"

    def test_normalizes_blank_lines(self) -> None:
        """Multiple blank lines → single blank line."""
        result = normalize_markdown_text("line 1\n\n\n\nline 2")
        assert result == "line 1\n\nline 2"

    def test_removes_trailing_blank_lines(self) -> None:
        """Trailing blank lines removed."""
        result = normalize_markdown_text("line 1\n\n")
        assert result == "line 1"

    def test_empty_string_unchanged(self) -> None:
        """Empty input is unchanged."""
        assert normalize_markdown_text("") == ""
