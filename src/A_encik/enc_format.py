"""ENC format parser and serializer for encik entries.

The .enc format is a TOML-based format for knowledge entries.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any


def parse_enc_file(path: Path) -> dict[str, Any]:
    """Parse an .enc file and return a dict with the entry fields.

    Args:
        path: Path to the .enc file

    Returns:
        Dictionary with entry fields

    Raises:
        ValueError: If the file is not a valid ENC file
    """
    raw = path.read_text(encoding="utf-8")

    # Extract title from first comment line (lines starting with #)
    titolo = ""
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("##"):
            candidate = stripped.lstrip("#").strip()
            if candidate:
                titolo = candidate
                break

    # Remove comment lines for TOML parsing
    toml_lines = []
    for line in raw.splitlines():
        if not line.strip().startswith("#"):
            toml_lines.append(line)
    toml_text = "\n".join(toml_lines)

    # Parse TOML
    try:
        data = tomllib.loads(toml_text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Nevalida ENC: {exc}") from exc

    # Build entry dict
    entry: dict[str, Any] = {}

    # titolo - from comment or from terminologio
    if titolo:
        entry["titolo"] = titolo
    if "titolo" in data:
        entry["titolo"] = data["titolo"]

    # difinio - simple definition
    if "difinio" in data:
        entry["difinio"] = data["difinio"]

    # terminologio - dict of language -> term
    if "terminologio" in data:
        entry["terminologio"] = data["terminologio"]

    # difinoj - dict of language -> definition
    if "difinoj" in data:
        entry["difinoj"] = data["difinoj"]
    elif "difino" in data:
        # Single language definition
        entry["difinoj"] = {"eo": data["difino"]}

    # enhavo - multiline content
    if "enhavo" in data:
        entry["enhavo"] = data["enhavo"]

    # superklaso - list of UUIDs
    if "superklaso" in data:
        entry["superklaso"] = data["superklaso"]
        if isinstance(entry["superklaso"], str):
            entry["superklaso"] = [entry["superklaso"]]

    # ligilo - list of UUIDs or [UUID, type] pairs
    if "ligilo" in data:
        entry["ligilo"] = data["ligilo"]

    # fonto - list of source dicts
    if "fonto" in data:
        entry["fonto"] = data["fonto"]

    # citajo - list of quote dicts
    if "citajo" in data:
        entry["citajo"] = data["citajo"]

    # datumo - dict of datasets
    if "datumo" in data:
        entry["datumo"] = data["datumo"]

    # semantika - list of semantic entries
    if "semantika" in data:
        entry["semantika"] = data["semantika"]

    # If no titolo, try to get from terminologio
    if "titolo" not in entry and entry.get("terminologio"):
        first_lang = next(iter(entry["terminologio"]), None)
        if first_lang:
            entry["titolo"] = entry["terminologio"][first_lang]

    if not entry.get("titolo"):
        raise ValueError("Nevalida ENC: titolo ne trovita")

    return entry


def entry_to_enc(entry: dict[str, Any]) -> str:
    """Serialize an encik entry to .enc format.

    Args:
        entry: Entry dictionary

    Returns:
        ENC formatted string
    """
    lines: list[str] = []

    # Title as comment
    titolo = entry.get("titolo", "")
    if titolo:
        lines.append(f"# {titolo}")
        lines.append("")

    # terminologio
    terminologio = entry.get("terminologio", {})
    if terminologio:
        for lang in sorted(terminologio):
            value = terminologio[lang]
            if "\n" in value:
                lines.append(f'terminologio.{lang} = """')
                lines.append(value)
                lines.append('"""')
            else:
                lines.append(f'terminologio.{lang} = {json.dumps(value, ensure_ascii=False)}')
        lines.append("")

    # difinoj
    difinoj = entry.get("difinoj", {})
    if difinoj:
        for lang in sorted(difinoj):
            value = difinoj[lang]
            if "\n" in value:
                lines.append(f'difino.{lang} = """')
                lines.append(value)
                lines.append('"""')
            else:
                lines.append(f'difino.{lang} = {json.dumps(value, ensure_ascii=False)}')
        lines.append("")

    # difinio (simple)
    if entry.get("difinio"):
        lines.append(f'difinio = {json.dumps(entry["difinio"], ensure_ascii=False)}')
        lines.append("")

    # enhavo
    if entry.get("enhavo"):
        lines.append('enhavo = """')
        lines.append(entry["enhavo"])
        lines.append('"""')
        lines.append("")

    # superklaso
    superklaso = entry.get("superklaso", [])
    if superklaso:
        lines.append(f"superklaso = {json.dumps(superklaso, ensure_ascii=False)}")
        lines.append("")

    # ligilo
    ligilo = entry.get("ligilo", [])
    if ligilo:
        lines.append(f"ligilo = {json.dumps(ligilo, ensure_ascii=False)}")
        lines.append("")

    # fonto
    fonto = entry.get("fonto", [])
    if fonto:
        lines.append("fonto = [")
        for src in fonto:
            items = []
            for k, v in src.items():
                if v:
                    items.append(f"{k} = {json.dumps(v, ensure_ascii=False)}")
            lines.append(f"  {{{', '.join(items)}}}")
        lines.append("]")
        lines.append("")

    # citajo
    citajo = entry.get("citajo", [])
    if citajo:
        lines.append("citajo = [")
        for c in citajo:
            items = []
            for k in ("teksto", "autoro", "verko", "jaro", "lingvo"):
                if c.get(k):
                    items.append(f"{k} = {json.dumps(c[k], ensure_ascii=False)}")
            lines.append(f"  {{{', '.join(items)}}}")
        lines.append("]")
        lines.append("")

    # datumo
    datumo = entry.get("datumo", {})
    if datumo:
        for name in sorted(datumo):
            payload = json.dumps(datumo[name], ensure_ascii=False, indent=2)
            lines.append(f'datumo.{name} = """')
            lines.append(payload)
            lines.append('"""')
        lines.append("")

    # semantika
    semantika = entry.get("semantika", [])
    if semantika:
        lines.append('semantika = """')
        for item in semantika:
            tipo = item.get("tipo", "")
            arko = item.get("arko", "")
            valoro = item.get("valoro", "")
            unuo = item.get("unuo", "")
            if tipo and arko:
                if unuo:
                    lines.append(f"{tipo} {arko} {valoro} #{unuo}")
                else:
                    lines.append(f"{tipo} {arko} {valoro}")
        lines.append('"""')
        lines.append("")

    return "\n".join(lines)


def validate_enc_entry(entry: dict[str, Any]) -> list[str]:
    """Validate an entry dict for required fields.

    Args:
        entry: Entry dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not entry.get("titolo"):
        errors.append("Mankas titolo")

    # Check at least one of terminologio or difinoj exists
    if not entry.get("terminologio") and not entry.get("difinoj"):
        errors.append("Mankas terminologio aŭ difinoj")

    return errors


__all__ = ["parse_enc_file", "entry_to_enc", "validate_enc_entry"]