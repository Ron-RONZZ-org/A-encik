""".enc file serializer — converts entry dicts to .enc format."""

from __future__ import annotations

import json
from typing import Any


def _decode_visible_newlines(value: str) -> str:
    """Decode escaped newlines (``\\n``) back to real newlines."""
    return value.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")


def _toml_list(lst: list) -> str:
    """Format a Python list as a compact TOML array."""
    if not lst:
        return "[]"
    return json.dumps(lst, ensure_ascii=False)


def _fonto_list(lst: list[dict]) -> str:
    """Format fonto entries as a TOML array of inline tables."""
    if not lst:
        return "[]"
    parts: list[str] = []
    for s in lst:
        items: list[str] = []
        for k, v in s.items():
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            if k == "jaro":
                items.append(f"{k} = {v}")
            else:
                items.append(f"{k} = {json.dumps(v, ensure_ascii=False)}")
        parts.append(f"{{{', '.join(items)}}}")
    return "[" + ", ".join(parts) + "]"


def _citajo_list(lst: list[dict]) -> str:
    """Format citajo entries as a TOML array of inline tables."""
    if not lst:
        return "[]"
    parts: list[str] = []
    for c in lst:
        items: list[str] = []
        for k in ("teksto", "autoro", "verko", "jaro", "lingvo"):
            raw = c.get(k)
            if raw is not None and str(raw).strip():
                items.append(f"{k} = {json.dumps(str(raw), ensure_ascii=False)}")
        parts.append(f"{{{', '.join(items)}}}")
    return "[" + ", ".join(parts) + "]"


def _datumo_block(datasets: dict) -> str:
    """Format datumo as TOML multi-line string blocks."""
    if not datasets:
        return ""
    lines: list[str] = []
    for name in sorted(datasets):
        payload = json.dumps(datasets[name], ensure_ascii=False, indent=2)
        lines.append(f'datumo.{name} = """\n{payload}\n"""')
    return "\n\n".join(lines)


def _semantika_block(items: list[dict]) -> str:
    """Format semantika entries as a TOML multi-line string."""
    if not items:
        return ""
    lines: list[str] = []
    for item in items:
        tipo = str(item.get("tipo") or "").strip().lower()
        arko = str(item.get("arko") or "").strip()
        valoro = str(item.get("valoro") or "").strip()
        unuo = str(item.get("unuo") or "").strip()
        if not tipo or not arko:
            continue
        if unuo:
            lines.append(f"{tipo} {arko} {valoro} #{unuo}")
        else:
            lines.append(f"{tipo} {arko} {valoro}")
    if not lines:
        return ""
    return 'semantika = """\n' + "\n".join(lines) + '\n"""'


def _lang_map_lines(prefix: str, mapping: dict[str, str]) -> str:
    """Format a language-to-string mapping as TOML dotted keys."""
    lines: list[str] = []
    for lang in sorted(mapping):
        value = _decode_visible_newlines(str(mapping[lang] or ""))
        if "\n" in value:
            safe = value.replace('"""', '\\"""')
            lines.append(f'{prefix}.{lang} = """\n{safe}\n"""')
        else:
            lines.append(f"{prefix}.{lang} = {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines)


def entry_to_enc(entry: dict[str, Any]) -> str:
    """Serialize an encik entry to .enc format.

    Args:
        entry: Entry dictionary

    Returns:
        ENC formatted string with explanatory comments
    """
    terminologio = entry.get("terminologio") or {}
    difinoj = entry.get("difinoj") or {}
    superklaso = entry.get("superklaso") or []
    ligilo = entry.get("ligilo") or []
    fonto = entry.get("fonto") or []
    citajo = entry.get("citajo") or []
    datumo = entry.get("datumo") or {}
    semantika = entry.get("semantika") or []
    enhavo = entry.get("enhavo", "")

    parts: list[str] = []

    # Title comment (from first terminologio value)
    for lang in ("eo", "en"):
        val = terminologio.get(lang)
        if val:
            parts.append(f"# {val}")
            parts.append("")
            break
    if not parts:
        for val in terminologio.values():
            if val:
                parts.append(f"# {val}")
                parts.append("")
                break

    # terminologio
    term_lines = _lang_map_lines("terminologio", terminologio)
    if term_lines:
        parts.append(term_lines)
        parts.append("")

    # difinoj
    dif_lines = _lang_map_lines("difino", difinoj)
    if dif_lines:
        parts.append(dif_lines)
        parts.append("")

    # enhavo
    if enhavo:
        parts.append('"""')
        parts.append(enhavo)
        parts.append('"""')
        parts.append("")

    # superklaso
    if superklaso:
        parts.append(f"# Superklasoj (retro-kongrue): UUID-oj au [Terminologio, UUID] paroj")
        parts.append(f"superklaso = {_toml_list(superklaso)}")
        parts.append("")

    # ligilo
    if ligilo:
        parts.append(
            "# Ligiloj: listo de UUID-oj au [UUID, semantika_tipo]\n"
            "# Ekzemploj:\n"
            '#   ligilo = "uuid1"\n'
            '#   ligilo = ["vt#8bf534dc"]\n'
            '#   ligilo = ["uuid1", "#uuid2", ["uuid3", "rdf:type"]]'
        )
        parts.append(f"ligilo = {_toml_list(ligilo)}")
        parts.append("")

    # fonto
    if fonto:
        parts.append(
            '# Fontoj: tabeloj kun titolo, autoro, jaro, tipo, noto, ligilo\n'
            '# Ekz: fonto = [{titolo="...", autoro="...", jaro=2020, tipo="lib"}]\n'
            '# Tipoj: lib(ro), art(ikolo), ret(ejo), fil(mo), tez(o), rap(orto), pod(kasto), pre(lego)'
        )
        parts.append(f"fonto = {_fonto_list(fonto)}")
        parts.append("")

    # citajo
    if citajo:
        parts.append("# Citajxoj: tabeloj {teksto, autoro, verko, jaro}")
        parts.append(f"citajo = {_citajo_list(citajo)}")
        parts.append("")

    # datumo
    datumo_str = _datumo_block(datumo)
    if datumo_str:
        parts.append(datumo_str)
        parts.append("")

    # semantika
    sem_str = _semantika_block(semantika)
    if sem_str:
        parts.append(sem_str)
        parts.append("")

    return "\n".join(parts)


__all__ = ["entry_to_enc"]
