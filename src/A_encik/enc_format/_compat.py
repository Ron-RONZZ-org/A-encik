"""Compatibility pre-processing for .enc files — ports legacy autish fixes."""

from __future__ import annotations

import re
from typing import Any


def normalize_multiline_value_spacing(raw: str) -> str:
    """Normalize spacing around multi-line TOML values.

    Adds a blank line before ``= \"\"\"`` to prevent TOML parse errors
    when content sits right after a key.
    """
    return re.sub(r'(?<=\S)\s*(\n\s*="""\s*\n)', r"\n\1", raw)


def expand_multi_locale_assignments(raw: str) -> str:
    """Expand shorthand ``terminologio.(eo,en)="value"`` to separate lines.

    Legacy autish allows: ``terminologio.(eo,en) = "Termo"``
    which expands to:
        terminologio.eo = "Termo"
        terminologio.en = "Termo"
    """
    pattern = re.compile(
        r"^(\s*[\w.]+)\.\(([^)]+)\)\s*=\s*(.*?)\s*$",
        re.MULTILINE,
    )
    def _replacer(m: re.Match) -> str:
        prefix = m.group(1)
        raw_langs = m.group(2)
        value = m.group(3)
        langs = [lang.strip() for lang in raw_langs.split(",") if lang.strip()]
        return "\n".join(f"{prefix}.{lang} = {value}" for lang in langs)

    return pattern.sub(_replacer, raw)


def escape_latex_style_backslashes(raw: str) -> str:
    """Escape LaTeX-style backslashes (``\\alpha``, ``\\uparrow``) in TOML strings.

    Legacy autish's TOML allowed ``\\alpha`` as a literal backslash; Python 3.11+'s
    tomllib is stricter. We must double-escape these before parsing.
    """
    result = []
    in_multiline = False
    in_singleline = False
    quote_char = None
    i = 0
    while i < len(raw):
        ch = raw[i]

        # Track string state
        if not in_multiline and not in_singleline:
            if ch in ('"', "'"):
                if raw[i : i + 3] in ('"""', "'''"):
                    in_multiline = True
                    quote_char = raw[i : i + 3]
                    result.append(raw[i : i + 3])
                    i += 3
                    continue
                else:
                    in_singleline = True
                    quote_char = ch
                    result.append(ch)
                    i += 1
                    continue
        elif in_multiline:
            if raw[i : i + 3] == quote_char:
                in_multiline = False
                quote_char = None
                result.append(raw[i : i + 3])
                i += 3
                continue
            # Inside multiline string: escape backslashes not already escaped
            if ch == "\\" and i + 1 < len(raw):
                next_ch = raw[i + 1]
                # Only keep quote-escapes as valid TOML escapes.
                # DO NOT include backslash — \\ is ambiguous: TOML treats it
                # as escaped backslash (\\) → \, but LaTeX needs \\ for line
                # breaks. We handle \\ differently based on the next char:
                #   \\ + letter → keep as TOML escape (e.g. \begin → \begin)
                #   \\ + space  → quadruple to preserve both backslashes
                #                 (e.g. \\ v → \\\\ v → TOML → \\ v ✓)
                #   \\ + " or ' → already handled below
                valid_escapes = {'"', "'"}
                # Already a valid TOML escape (quote)
                if next_ch in valid_escapes:
                    result.append(ch)
                    result.append(next_ch)
                    i += 2
                    continue
                # TOML line continuation: backslash at end of line
                if next_ch == "\n":
                    result.append(ch)
                    result.append(next_ch)
                    i += 2
                    continue
                # LaTeX line break: \\ followed by space
                if next_ch == "\\" and i + 2 < len(raw) and raw[i + 2] == " ":
                    # Quadruple to \\\\ → TOML produces \\
                    result.append("\\\\\\\\")
                    i += 2
                    continue
                # LaTeX command: \\ followed by letter → keep as valid escape
                # (e.g. \\begin → TOML \\ → \, then "begin")
                if next_ch == "\\":
                    result.append(ch)
                    result.append(next_ch)
                    i += 2
                    continue
                # Single backslash before any other char — LaTeX style
                result.append("\\\\")
                i += 1
                continue
        elif in_singleline:
            if ch == quote_char and (i == 0 or raw[i - 1] != "\\"):
                in_singleline = False
                quote_char = None
                result.append(ch)
                i += 1
                continue
            if ch == "\\" and i + 1 < len(raw):
                next_ch = raw[i + 1]
                # Same logic as multiline: handle \\ + space specially
                valid_escapes = {'"', "'"}
                if next_ch in valid_escapes:
                    result.append(ch)
                    result.append(next_ch)
                    i += 2
                    continue
                # LaTeX line break: \\ followed by space
                if next_ch == "\\" and i + 2 < len(raw) and raw[i + 2] == " ":
                    result.append("\\\\\\\\")
                    i += 2
                    continue
                # LaTeX command: \\ followed by letter → keep as escape
                if next_ch == "\\":
                    result.append(ch)
                    result.append(next_ch)
                    i += 2
                    continue
                # Single backslash before any other char — LaTeX style
                result.append("\\\\")
                i += 1
                continue

        result.append(ch)
        i += 1

    return "".join(result)


def fix_inline_table_commas(text: str) -> str:
    """Add missing commas between fields in inline tables (``fonto`` blocks).

    Legacy autish allowed: ``{titolo="..." autoro="..."}``
    But TOML requires: ``{titolo="...", autoro="..."}``
    """
    result = []
    brace_depth = 0
    prev_char = ""
    for ch in text:
        if ch == "{":
            brace_depth += 1
            result.append(ch)
        elif ch == "}":
            brace_depth -= 1
            result.append(ch)
        elif ch == "=" and brace_depth > 0 and prev_char in ('"', "'"):
            # This is inside an inline table, after a string value
            # which might be missing a comma before the next key=value
            result.append(ch)
        else:
            # After a closing quote inside inline table, if next non-space is
            # alphanumeric or _, add a comma
            result.append(ch)
            if brace_depth > 0 and ch in ('"', "'") and prev_char != "\\":
                # Look ahead for missing comma
                j = len(result)
                while j < len(text) and text[j] in " \t":
                    j += 1
                if j < len(text) and text[j] not in ("}", ",", "]"):
                    result.append(", ")
                    # skip the original space
        prev_char = ch

    return "".join(result)


def fix_unquoted_uuids(text: str) -> str:
    """Quote bare UUIDs in TOML array values.

    Legacy autish allowed: ``ligilo = [uuid1, uuid2]``
    But TOML requires quoted strings: ``ligilo = ["uuid1", "uuid2"]``
    """
    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        # Look for bare hex strings inside arrays
        if ch in ("[", ","):
            result.append(ch)
            i += 1
            # Skip whitespace
            while i < len(text) and text[i] in " \t":
                result.append(text[i])
                i += 1
            # Check if next is a bare UUID (hex string without quotes)
            if i < len(text) and re.match(
                r"^[0-9a-fA-F]{8,}(?:\s*[,\}\]])",
                text[i:],
            ):
                # Extract the UUID
                match = re.match(r"([0-9a-fA-F]{8,})", text[i:])
                if match:
                    uuid_val = match.group(1)
                    result.append(f'"{uuid_val}"')
                    i += len(uuid_val)
                    continue
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def extract_enhavo_block(raw: str) -> tuple[str, str]:
    """Extract a standalone ``\"\"\"...\"\"\"`` block as enhavo content.

    Legacy autish allowed a bare ``\"\"\"...\"\"\"`` at the top level
    to define ``enhavo`` without an ``enhavo = `` prefix.

    Returns (stripped_toml, extracted_enhavo).
    """
    stripped_core = raw
    extracted = ""

    # Find a standalone """ block (not preceded by =)
    pattern = re.compile(r'(?<!=)\s*"""\n(.*?)\n"""', re.DOTALL)
    match = pattern.search(raw)
    if match:
        extracted = match.group(1).strip()
        # Remove the block from the text
        stripped_core = raw[: match.start()] + raw[match.end() :]

    return stripped_core, extracted


def normalize_markdown_text(text: str) -> str:
    """Normalize markdown content in definitions and content.

    Fixes heading spacing, removes trailing whitespace, normalizes
    blank lines.
    """
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.rstrip()
        if stripped and stripped[0] == "#" and len(stripped) > 1 and stripped[1] != "#":
            stripped = re.sub(r"^#(\S)", r"# \1", stripped)
        result.append(stripped)
    # Remove trailing blank lines
    while result and not result[-1].strip():
        result.pop()
    # Normalize multiple blank lines to at most one
    normalized: list[str] = []
    blank_count = 0
    for line in result:
        if not line.strip():
            blank_count += 1
            if blank_count <= 1:
                normalized.append("")
        else:
            blank_count = 0
            normalized.append(line)
    return "\n".join(normalized)


__all__ = [
    "normalize_multiline_value_spacing",
    "expand_multi_locale_assignments",
    "escape_latex_style_backslashes",
    "fix_inline_table_commas",
    "fix_unquoted_uuids",
    "extract_enhavo_block",
    "normalize_markdown_text",
]
