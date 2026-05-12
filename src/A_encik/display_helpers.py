"""Display helpers for encik CLI — ported from autish-legacy patterns.

Provides language selection, markdown→Rich rendering, ligilo formatting,
candidate tables, and clipboard helpers for `ls`, `vidi`, and `serci`.
"""

from __future__ import annotations

import os
import re
from typing import Any

from rich.table import Table
from rich.text import Text

from A import info, copy_to_clipboard, tr_multi
from A.console import console


# ──────────────────────────────────────────────────────────────────────────────
# Language helpers
# ──────────────────────────────────────────────────────────────────────────────


def preferred_lang(
    terminologio: dict[str, str],
    difinoj: dict[str, str],
) -> str:
    """Select the best language from terminologio + difinoj.

    Priority:
    1. LC_ALL/LANG env var (if both term+def exist)
    2. ``"eo"`` (if both exist)
    3. ``"en"`` (if both exist)
    4. First language shared between term and def
    5. First available term language
    6. First available def language
    7. ``""``

    Examples:
        >>> preferred_lang({"eo": "testo", "en": "test"}, {"eo": "difino"})
        'eo'
    """
    # Env language
    raw_env = os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
    env_lang = raw_env.split(".")[0].split("_")[0].lower()
    if env_lang and terminologio.get(env_lang) and difinoj.get(env_lang):
        return env_lang

    for lang in ("eo", "en"):
        if terminologio.get(lang) and difinoj.get(lang):
            return lang

    shared = [lang for lang in terminologio if difinoj.get(lang)]
    if shared:
        return shared[0]
    if terminologio:
        return next(iter(terminologio.keys()))
    if difinoj:
        return next(iter(difinoj.keys()))
    return ""


def entry_locale_title(
    entry: dict,
    preferred_langs: list[str] | None = None,
) -> str:
    """Get the best display title from *terminologio* based on language preferences.

    Priority:
    1. Explicit *preferred_langs* (from ``--lingvo``)
    2. Environment language (LC_ALL/LANG)
    3. ``"eo"``
    4. ``"en"``
    5. ``entry["titolo"]``
    6. First available terminologio value

    Examples:
        >>> entry_locale_title({"titolo": "Test", "terminologio": {"eo": "testo"}})
        'testo'
    """
    term = entry.get("terminologio") or {}

    if preferred_langs:
        for lang in preferred_langs:
            if term.get(lang):
                return str(term[lang])

    raw_env = os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
    env_lang = raw_env.split(".")[0].split("_")[0].lower()
    if env_lang and term.get(env_lang):
        return str(term[env_lang])

    for lang in ("eo", "en"):
        if term.get(lang):
            return str(term[lang])

    return str(entry.get("titolo") or next(iter(term.values()), ""))


def normalize_lingvo_codes(raw: str | None, field: str = "--lingvo") -> list[str]:
    """Parse ``\"eo,en,fr\"`` into ``[\"eo\", \"en\", \"fr\"]``.

    Validates 2-letter codes. Raises ``ValueError`` on invalid input.
    """
    if not raw:
        return []
    codes = [c.strip().lower() for c in raw.split(",") if c.strip()]
    for code in codes:
        if not re.fullmatch(r"[a-z]{2}", code):
            raise ValueError(
                tr_multi(
                    f"Nevalida lingvokodo en {field}: {code!r} (uzu 2-literajn kodojn)",
                    f"Invalid language code in {field}: {code!r} (use 2-letter codes)",
                )
            )
    return codes


# ──────────────────────────────────────────────────────────────────────────────
# Markdown rendering
# ──────────────────────────────────────────────────────────────────────────────


_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC = re.compile(r"\*(.+?)\*")
_MD_CODE = re.compile(r"`(.+?)`")
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def has_non_cli_renderable_markup(text: str) -> bool:
    """Check if *text* contains KaTeX (``$$..$$``, ``$..$``), images (``![]()``), or ``<img>``.

    These require a browser to render properly.
    """
    if not text:
        return False
    return bool(
        re.search(r"\$\$", text)
        or re.search(r"(?<!\$)\$(?!\$)", text)
        or _MD_IMAGE.search(text)
        or re.search(r"<\s*img\s+", text, re.IGNORECASE)
    )


def render_markdown_text(text: str) -> str:
    """Convert markdown to Rich markup for CLI display.

    Transformations:
    - ``**bold**`` → Rich bold
    - ``*italic*`` → Rich italic
    - ```code``` → Rich code
    - ``[text](url)`` → Rich link (if external) or plain label
    - ``![]()`` stripped (images not renderable in CLI)
    """
    if not text:
        return ""

    # Strip images
    text = _MD_IMAGE.sub(r"\1", text)

    # Convert links: [label](url) → [label](url) for http, or just label
    def _link_repl(m: re.Match) -> str:
        label = m.group(1)
        url = m.group(2)
        if url.startswith("http://") or url.startswith("https://"):
            return f"[link={url}]{label}[/link]"
        # Internal refs (ec#, vt#) — just show label
        return label

    text = _MD_LINK.sub(_link_repl, text)

    # Convert markdown to Rich markup
    text = _MD_BOLD.sub(r"[bold]\1[/bold]", text)
    text = _MD_ITALIC.sub(r"[italic]\1[/italic]", text)
    text = _MD_CODE.sub(r"[code]\1[/code]", text)

    return text


# ──────────────────────────────────────────────────────────────────────────────
# Ligilo formatting
# ──────────────────────────────────────────────────────────────────────────────


def _semantika_description(tipo: str | None) -> str | None:
    """Look up a human-readable description for a semantika link type."""
    if not tipo:
        return None
    from A_encik.semantika.config import normalize_semantika_ligilo

    canonical = normalize_semantika_ligilo(tipo)
    if not canonical:
        return tipo

    from A_encik.semantika.config import _SEMANTIKA_DEFINOJ_MAP

    entry = _SEMANTIKA_DEFINOJ_MAP.get(canonical)
    if entry:
        return str(entry[0])
    return canonical


# Priority ranking for semantic link types in display
_SEM_RANK: dict[str, int] = {
    "rdf:type": 0,
    "rdfs:subClassOf": 1,
    "owl:inverseOf": 2,
    "owl:disjointWith": 3,
}


def _sem_rank(tipo: str | None) -> int:
    """Rank a semantika type for display ordering."""
    if not tipo:
        return 99
    return _SEM_RANK.get(tipo, 4)


def display_ligilo_items(entry: dict) -> list[dict]:
    """Resolve and format the ligilo entries of an *entry*.

    Returns a list of ``{"uuid": str, "tipo": str | None, "titolo": str}``
    with semantic types normalised and deduplicated.
    """
    from A_encik.semantika.config import normalize_semantika_ligilo

    items: list[dict] = []
    seen: set[str] = set()

    ligilo = entry.get("ligilo") or []
    if isinstance(ligilo, str):
        ligilo = [ligilo]

    for item in ligilo:
        if isinstance(item, list):
            uuid = str(item[0]) if item else ""
            tipo_raw = str(item[1]) if len(item) > 1 else ""
        elif isinstance(item, str):
            uuid = item
            tipo_raw = ""
        else:
            continue

        uuid = uuid.strip()
        if not uuid or uuid in seen:
            continue
        seen.add(uuid)

        tipo = normalize_semantika_ligilo(tipo_raw) if tipo_raw else None
        items.append({"uuid": uuid, "tipo": tipo})

    # Also merge superklaso as rdfs:subClassOf links
    superklaso = entry.get("superklaso") or []
    if isinstance(superklaso, str):
        superklaso = [superklaso]
    for parent_ref in superklaso:
        parent_ref = parent_ref.strip() if isinstance(parent_ref, str) else ""
        if parent_ref and parent_ref not in seen:
            seen.add(parent_ref)
            items.append({"uuid": parent_ref, "tipo": "rdfs:subClassOf"})

    # Resolve titles
    from A_encik.service import get_service

    svc = get_service()
    for item in items:
        resolved = svc.get(item["uuid"])
        if resolved:
            item["titolo"] = entry_locale_title(resolved)
        else:
            # Try prefix match
            matches = svc.find_by_uuid_prefix(item["uuid"])
            if matches:
                item["titolo"] = entry_locale_title(matches[0])
            else:
                item["titolo"] = item["uuid"][:8]

    return items


# ──────────────────────────────────────────────────────────────────────────────
# Candidate table
# ──────────────────────────────────────────────────────────────────────────────


def print_candidates_table(
    candidates: list[dict],
    preferred_langs: list[str] | None = None,
) -> None:
    """Print a numbered Rich table with ``#``, ``UUID``, and ``Titolo`` columns.

    Uses :func:`entry_locale_title` for the title column.
    """
    table = Table(show_header=True, box=None)
    table.add_column("#", width=3)
    table.add_column("UUID", width=10)
    table.add_column("Titolo")
    for i, entry in enumerate(candidates, 1):
        display_title = entry_locale_title(entry, preferred_langs=preferred_langs)
        table.add_row(str(i), entry.get("uuid", "")[:8], display_title)
    console.print(table)


# ──────────────────────────────────────────────────────────────────────────────
# Clipboard helpers
# ──────────────────────────────────────────────────────────────────────────────


def copy_entry_reference(
    entry: dict,
    *,
    semantika: bool = False,
) -> None:
    """Copy entry reference to clipboard.

    Simple: copies ``#xxxxxxxx`` (8-char UUID).
    Semantika: copies ``[titolo](#xxxxxxxx)``.
    """
    uid = entry.get("uuid", "")[:8]
    if semantika:
        title = entry_locale_title(entry)
        copy_to_clipboard(f"[{title}](#{uid})")
    else:
        copy_to_clipboard(f"#{uid}")


# ──────────────────────────────────────────────────────────────────────────────
# Browser fallback
# ──────────────────────────────────────────────────────────────────────────────


__all__ = [
    "preferred_lang",
    "entry_locale_title",
    "normalize_lingvo_codes",
    "has_non_cli_renderable_markup",
    "render_markdown_text",
    "display_ligilo_items",
    "print_candidates_table",
    "copy_entry_reference",
    "_sem_rank",
    "_semantika_description",
]
