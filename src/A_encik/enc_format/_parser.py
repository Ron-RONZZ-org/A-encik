""".enc file parser with compatibility support for legacy autish format."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import tomllib

from A_encik.enc_format._compat import (
    normalize_multiline_value_spacing,
    expand_multi_locale_assignments,
    escape_latex_style_backslashes,
    fix_inline_table_commas,
    fix_unquoted_uuids,
    extract_enhavo_block,
    normalize_markdown_text,
)

# Valid .enc keys
VALID_ENC_KEYS = frozenset({
    "titolo", "difinio", "difino", "difinoj",
    "terminologio",
    "enhavo",
    "superklaso",
    "ligilo",
    "fonto", "source",
    "citajo",
    "datumo",
    "semantika",
    "noto",
})

# TOML dotted keys are allowed (e.g., terminologio.eo, datumo.name)
# so we only check top-level keys


def _format_enc_parse_error(raw: str, exc: Exception) -> str:
    """Format a TOML parse error with line/col hints for .enc context."""
    msg = str(exc)
    lowered = msg.lower()

    # Build hints based on error type
    hints: list[str] = []
    if "cannot overwrite a value" in lowered:
        hints.append(
            "Sama kampo aperas plurfoje. .enc dosiero rajtas enteni nur unu eniron; "
            "forigu duplikat(ajn) kampon(j)n aŭ dividu en apartajn dosierojn."
        )
    if "invalid value" in lowered:
        hints.append(
            "Kontrolu ĉu tekstoj estas en citiloj kaj listoj/tabeloj estas "
            "ĝuste fermitaj per ] aŭ }."
        )
    if "expected '=' after a key" in lowered:
        hints.append("Verŝajne mankas '=' inter kampnomo kaj valoro.")
    if "unterminated" in lowered or "unclosed" in lowered:
        hints.append("Mankas ferma citilo, ] aŭ }.")
    if "expected newline" in lowered and "after a statement" in lowered:
        hints.append(
            "Ĉu ne-cititaj valoroj en tabelo (ligilo/superklaso)? "
            "Citiloj bezonatas por tekstoj: ligilo = [\"uuid\", \"tipo\"], "
            "ne ligilo = [uuid, tipo]"
        )
        hints.append(
            "Formato por ligilo: ligilo = [[\"uuid\", \"tipo\"], ...] "
            "aŭ ligilo = [\"uuid1\", \"uuid2\"]"
        )

    # Try to extract line number from TOML error
    match = re.search(r"line (\d+), col (\d+)", msg)
    if match:
        line_no = int(match.group(1))
        lines = raw.splitlines()
        if 1 <= line_no <= len(lines):
            context = lines[line_no - 1].strip()
            if len(context) > 80:
                context = context[:77] + "..."
            result = (
                f"Sintaksa eraro ĉe linio {line_no} (kolumno {match.group(2)}):\n"
                f"  {context}\n"
                f"  {msg}"
            )
            if hints:
                result += "\n" + "\n".join(f"  * {h}" for h in hints)
            return result

    result = f"Nevalida .enc: {msg}"
    if hints:
        result += "\n" + "\n".join(f"  * {h}" for h in hints)
    return result


def _validate_enc_keys(data: dict) -> None:
    """Validate top-level keys, providing suggestions for misspellings."""
    for key in data:
        if key in VALID_ENC_KEYS:
            continue
        # Check if it's a dotted key (e.g., terminologio.eo, datumo.x)
        base = key.split(".")[0]
        if base in VALID_ENC_KEYS:
            continue
        # Provide suggestions for close matches
        suggestions = [k for k in VALID_ENC_KEYS if len(set(k) ^ set(key)) <= 3]
        if suggestions:
            raise ValueError(
                f"Nekonata kampo: '{key}'. Ĉu vi volis: {', '.join(suggestions)}?"
            )
        raise ValueError(f"Nekonata kampo: '{key}'.")


def _has_minimum_term_definition_pair(
    terminologio: dict[str, str], difinoj: dict[str, str]
) -> bool:
    """Check that at least one language has both a term and a definition."""
    common = set(terminologio) & set(difinoj)
    if common:
        return True
    # Allow if there's at least a term or a definition
    return bool(terminologio) or bool(difinoj)


def _collect_lang_fields(data: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Collect terminologio and difinoj from parsed TOML data.

    Handles both flat dotted keys (terminologio.eo = "...") and
    table syntax (terminologio = {eo = "..."}).
    """
    terminologio: dict[str, str] = {}
    difinoj: dict[str, str] = {}

    for key in data:
        parts = key.split(".", 1)
        base = parts[0]

        if base == "terminologio":
            val = data[key]
            if len(parts) == 2:
                # terminologio.eo = "..."
                if isinstance(val, str):
                    terminologio[parts[1]] = val
            elif isinstance(val, dict):
                # terminologio = {eo = "...", ...}
                terminologio.update({k: str(v) for k, v in val.items() if isinstance(v, str)})
            elif isinstance(val, str):
                terminologio["eo"] = val

        elif base == "difino" or base == "difinoj":
            val = data[key]
            if len(parts) == 2:
                if isinstance(val, str):
                    lang = parts[1]
                    # Handle both difino.en and difinoj.en
                    difinoj[lang] = val
            elif isinstance(val, dict):
                difinoj.update({k: str(v) for k, v in val.items() if isinstance(v, str)})
            elif isinstance(val, str):
                difinoj["eo"] = val

    return terminologio, difinoj


def _normalise_fonto_tipo(raw_tipo: str) -> str:
    """Normalise fonte type aliases to canonical forms."""
    tipo_map = {
        "lib": "libro", "libroj": "libro",
        "art": "artikolo", "artikoloj": "artikolo",
        "ret": "retejo", "retejoj": "retejo",
        "fil": "filmo", "filmoj": "filmo",
        "tez": "tezo", "tezoj": "tezo",
        "rap": "raporto", "raportoj": "raporto",
        "pod": "podkasto", "podkastoj": "podkasto",
        "pre": "prelego", "prelegoj": "prelego",
    }
    normalized = raw_tipo.strip().lower()
    return tipo_map.get(normalized, normalized)


def _normalise_superklaso_refs(raw: Any) -> list[str]:
    """Normalise superklaso references to a list of UUID strings.

    Strips leading ``#`` from any reference (some .enc files store
    them with the autish-legacy ``#`` prefix convention).
    """
    def _clean(val: str) -> str:
        return val.strip().lstrip("#")

    if isinstance(raw, str):
        return [_clean(raw)]
    if isinstance(raw, list):
        result: list[str] = []
        for item in raw:
            if isinstance(item, str):
                result.append(_clean(item))
            elif isinstance(item, list) and len(item) >= 2:
                # [title, UUID] pair — take the UUID
                result.append(_clean(str(item[1])))
        return result
    return []


def _normalize_lingvo_codes(raw: str, field: str = "") -> list[str]:
    """Parse and validate language codes (e.g. 'eo, en, fr')."""
    if not raw:
        return []
    codes = [c.strip().lower() for c in str(raw).split(",") if c.strip()]
    valid = [c for c in codes if re.fullmatch(r"[a-z]{2}", c)]
    return valid


def _looks_like_uuid(s: str) -> bool:
    """Check if a string looks like a UUID (8+ hex chars with optional hyphens/dots)."""
    cleaned = s.lstrip("#").replace("-", "").replace(".", "")
    return bool(re.fullmatch(r"[0-9a-fA-F]{8,}", cleaned))


def _normalise_ligilo_flat_list(raw: list) -> list:
    """Convert flat ``[uuid, tipo, uuid, tipo]`` to ``[[uuid, tipo], [uuid, tipo]]``.

    Legacy .enc files sometimes store ligilo as a flat list where
    non-UUID strings are interpreted as the semantic type of the
    preceding UUID. This function detects and converts that format.

    Examples::

        [\"15ab7b6c\", \"owl:disjointWith\"]           → [[\"15ab7b6c\", \"owl:disjointWith\"]]
        [\"abc123\", \"def456\"]                       → [[\"abc123\"], [\"def456\"]]
        [[\"uuid1\", \"rdf:type\"], [\"uuid2\"]]      → unchanged (already nested)
    """
    # Already nested — nothing to do
    if any(isinstance(item, list) for item in raw):
        return raw

    result: list[list[str]] = []
    current_uuid: str | None = None
    for item in raw:
        s = str(item).strip()
        if _looks_like_uuid(s):
            if current_uuid is not None:
                result.append([current_uuid])
            current_uuid = s
        else:
            # Non-UUID string with preceding UUID → pair as [uuid, tipo]
            if current_uuid is not None:
                result.append([current_uuid, s])
                current_uuid = None
            else:
                # Orphaned tipo with no preceding UUID → treat as bare link
                result.append([s])
    if current_uuid is not None:
        result.append([current_uuid])
    return result


def parse_enc_file(path: Path) -> dict[str, Any]:
    """Parse an .enc file and return a dict with the entry fields.

    The .enc format is TOML with:
    - Optional leading comment ``# Title`` used as the primary title
    - ``terminologio.{lang} = "term"`` for multi-language terms
    - ``difino.{lang} = "def"`` for multi-language definitions
    - ``enhavo = \"\"\"...\"\"\"`` for multi-line content
    - Compatibility with legacy autish syntax (unquoted UUIDs, missing commas, etc.)

    Args:
        path: Path to the .enc file

    Returns:
        Dictionary with entry fields

    Raises:
        ValueError: If the file is not a valid ENC file
    """
    raw = path.read_text(encoding="utf-8")

    # Pre-processing (legacy compatibility)
    raw = normalize_multiline_value_spacing(raw)
    raw = expand_multi_locale_assignments(raw)
    raw = escape_latex_style_backslashes(raw)
    raw = fix_inline_table_commas(raw)
    raw = fix_unquoted_uuids(raw)

    # Extract title from first comment line
    title_from_comment = ""
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("##"):
            candidate = stripped.lstrip("#").strip()
            if candidate:
                title_from_comment = candidate
                break

    # Parse TOML (comments are automatically ignored)
    enhavo = ""
    raw_core = raw
    try:
        data = tomllib.loads(raw_core)
    except tomllib.TOMLDecodeError as exc:
        stripped_core, extracted_enhavo = extract_enhavo_block(raw)
        if stripped_core != raw:
            try:
                data = tomllib.loads(stripped_core)
                raw_core = stripped_core
                enhavo = extracted_enhavo
            except tomllib.TOMLDecodeError:
                raise ValueError(_format_enc_parse_error(raw_core, exc)) from exc
        else:
            raise ValueError(_format_enc_parse_error(raw_core, exc)) from exc

    _validate_enc_keys(data)

    terminologio, difinoj = _collect_lang_fields(data)

    # Fallback: use title from comment if no terminologio
    if not terminologio and title_from_comment:
        terminologio = {"eo": title_from_comment}

    # Fallback: use difinio/difino as eo difinoj
    if not difinoj:
        for candidate in ("difinio", "difino"):
            raw_val = data.get(candidate, "")
            if isinstance(raw_val, str) and raw_val.strip():
                difinoj["eo"] = raw_val.strip()
                break

    # Normalize markdown in definitions
    difinoj = {lang: normalize_markdown_text(text) for lang, text in difinoj.items()}

    if not _has_minimum_term_definition_pair(terminologio, difinoj):
        raise ValueError(
            "Nevalida .enc: bezonata almenaŭ unu lingvo kun ambaŭ "
            "terminologio.xx kaj difino.xx."
        )

    titolo = next(iter(terminologio.values()))
    difinio = difinoj.get(next(iter(terminologio.keys())), "")
    if not difinio and difinoj:
        difinio = next(iter(difinoj.values()))

    # Build entry dict (no primary titolo — all terminologio values are equal)
    entry: dict[str, Any] = {
        "terminologio": terminologio,
        "difinoj": difinoj,
    }
    if difinio:
        entry["difinio"] = difinio

    # enhavo
    entry_enhavo = data.get("enhavo", enhavo)
    if isinstance(entry_enhavo, str) and entry_enhavo.strip():
        entry["enhavo"] = entry_enhavo

    # superklaso
    superklaso = _normalise_superklaso_refs(data.get("superklaso", []))
    if superklaso:
        entry["superklaso"] = superklaso

    # ligilo
    raw_ligilo = data.get("ligilo", [])
    if isinstance(raw_ligilo, str):
        raw_ligilo = [raw_ligilo]
    if raw_ligilo:
        entry["ligilo"] = _normalise_ligilo_flat_list(raw_ligilo)

    # fonto
    raw_fonto = data.get("fonto", data.get("source", []))
    if raw_fonto:
        fonto: list[dict] = []
        for item in raw_fonto:
            if isinstance(item, dict):
                normalized: dict[str, Any] = {}
                for k, v in item.items():
                    kl = k.lower()
                    if kl in ("titolo", "title"):
                        normalized["titolo"] = str(v)
                    elif kl in ("autoro", "author"):
                        normalized["autoro"] = str(v)
                    elif kl in ("jaro", "year"):
                        try:
                            normalized["jaro"] = int(v)
                        except (ValueError, TypeError):
                            normalized["jaro"] = v
                    elif kl in ("tipo", "type"):
                        normalized["tipo"] = _normalise_fonto_tipo(str(v))
                    elif kl in ("lingvo", "language", "lang"):
                        codes = _normalize_lingvo_codes(str(v), "fonto.lingvo")
                        if codes:
                            normalized["lingvo"] = ",".join(codes)
                    elif kl == "noto":
                        normalized["noto"] = str(v)
                    elif kl == "ligilo":
                        normalized["ligilo"] = str(v)
                    else:
                        normalized[k] = str(v)
                fonto.append(normalized)
        entry["fonto"] = fonto

    # citajo
    raw_citajo = data.get("citajo", [])
    if raw_citajo:
        citajo: list[dict] = []
        for item in raw_citajo:
            if not isinstance(item, dict):
                continue
            normalized_quote: dict[str, str] = {}
            for key in ("teksto", "autoro", "verko", "jaro", "lingvo"):
                raw_val = item.get(key)
                if raw_val is not None and str(raw_val).strip():
                    normalized_quote[key] = str(raw_val).strip()
            if normalized_quote:
                citajo.append(normalized_quote)
        entry["citajo"] = citajo

    # datumo
    raw_datumo = data.get("datumo", {})
    if isinstance(raw_datumo, dict) and raw_datumo:
        entry["datumo"] = raw_datumo

    # semantika
    raw_semantika = data.get("semantika", "")
    if isinstance(raw_semantika, str) and raw_semantika.strip():
        entry["semantika"] = raw_semantika
    elif isinstance(raw_semantika, list) and raw_semantika:
        entry["semantika"] = raw_semantika

    return entry


__all__ = ["parse_enc_file"]
