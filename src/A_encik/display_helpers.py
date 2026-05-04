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

from A import info, copy_to_clipboard
from A.console import console, tr


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
                tr(
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
    table = Table(show_header=True, header_style="dim", box=None)
    table.add_column("#", style="dim", width=3)
    table.add_column("UUID", style="dim", width=10)
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


def browser_fallback_hint() -> str:
    """Return a hint to use ``-H`` for content that needs a browser."""
    return tr(
        "Uzu -H por malfermi en retumilo por KaTeX/bildoj",
        "Use -H to open in browser for KaTeX/images",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Entry Panel display
# ──────────────────────────────────────────────────────────────────────────────


def _sem_rank(tipo: str | None) -> int:
    """Rank a semantic link type for display ordering."""
    if not tipo:
        return 99
    _RANK: dict[str, int] = {
        "rdf:type": 0,
        "rdfs:subClassOf": 1,
        "owl:inverseOf": 2,
        "owl:disjointWith": 3,
    }
    return _RANK.get(tipo, 4)


def _semantika_description(tipo: str | None) -> str | None:
    """Look up a human-readable description for a semantic link type."""
    if not tipo:
        return None
    from A_encik.semantika.config import normalize_semantika_ligilo

    canonical = normalize_semantika_ligilo(tipo)
    if not canonical:
        return tipo
    from A_encik.semantika.config import _SEMANTIKA_DEFINOJ_MAP

    entry = _SEMANTIKA_DEFINOJ_MAP.get(canonical)
    return str(entry[0]) if entry else canonical


def display_entry_panel(
    entry: dict,
    *,
    selected_lang: str = "",
    cxio: bool = False,
) -> None:
    """Display a knowledge entry as a styled Rich Panel.

    Args:
        entry: Entry dictionary.
        selected_lang: Preferred language code (auto-detected if empty).
        cxio: Show all languages and fields if True.
    """
    from rich.panel import Panel

    terminologio = entry.get("terminologio") or {}
    difinoj = entry.get("difinoj") or {}
    if not selected_lang:
        selected_lang = preferred_lang(terminologio, difinoj)
    title = entry_locale_title(entry, [selected_lang] if selected_lang else None)

    lines: list[str] = []
    LW = 14  # label width

    # Header
    lines.append(f"  [dim]{'uuid:':<{LW}}[/dim] {entry.get('uuid', '')[:8]}")
    lines.append(f"  [dim]{'lingvo:':<{LW}}[/dim] {selected_lang or '-'}")

    # Terminologio (all langs if --cxio)
    if cxio and terminologio:
        lines.append(f"  [dim]{'terminologio:':<{LW}}[/dim]")
        for lang, term in sorted(terminologio.items()):
            lines.append(f"    {lang}: {render_markdown_text(term)}")

    # Difino (preferred language)
    difinio = (
        difinoj.get(selected_lang)
        or entry.get("difinio", "")
        or next(iter(difinoj.values()), "")
    ).strip()
    if difinio:
        if has_non_cli_renderable_markup(difinio):
            lines.append(f"  [dim]{'difino:':<{LW}}[/dim]")
            lines.append(f"    [dim]{browser_fallback_hint()}[/dim]")
        else:
            lines.append(f"  [dim]{'difino:':<{LW}}[/dim]")
            for ln in difinio.splitlines():
                lines.append(f"    {render_markdown_text(ln)}")

    # All difinoj (if --cxio)
    if cxio and difinoj:
        lines.append(f"  [dim]{'difinoj:':<{LW}}[/dim]")
        for lang, term_def in sorted(difinoj.items()):
            lines.append(f"    {lang}: {render_markdown_text(term_def)}")

    # Enhavo (if --cxio)
    enhavo = (entry.get("enhavo") or "").strip()
    if enhavo and cxio:
        if has_non_cli_renderable_markup(enhavo):
            lines.append(f"  [dim]{'enhavo:':<{LW}}[/dim]")
            lines.append(f"    [dim]{browser_fallback_hint()}[/dim]")
        else:
            lines.append(f"  [dim]{'enhavo:':<{LW}}[/dim]")
            for ln in enhavo.splitlines():
                ln_stripped = ln.strip()
                if ln_stripped:
                    lines.append(f"    {render_markdown_text(ln_stripped)}")

    # Subklaso (if --cxio)
    if cxio:
        entry_uuid = entry.get("uuid")
        if entry_uuid:
            from A_encik.service import get_service as _gs
            subclasses = _gs().get_subclasses(entry_uuid, max_depth=1)
            if subclasses:
                lines.append(f"  [dim]{'subklaso:':<{LW}}[/dim]")
                for child in subclasses:
                    child_entry = child["entry"]
                    child_title = entry_locale_title(child_entry)
                    lines.append(f"    {child_title}  [dim]#{child_entry.get('uuid', '')[:8]}[/dim]")

    # Ligilo
    ligilo_items = display_ligilo_items(entry)
    if ligilo_items:
        grouped: dict[str, list[dict]] = {}
        for item in ligilo_items:
            tipo = item.get("tipo") or ""
            if tipo not in grouped:
                grouped[tipo] = []
            grouped[tipo].append(item)

        for tipo in sorted(grouped, key=lambda t: _sem_rank(t)):
            items = grouped[tipo]
            items.sort(key=lambda x: (x.get("titolo") or "").lower())
            desc = _semantika_description(tipo) or tipo
            for item in items:
                linked_title = item.get("titolo", item["uuid"][:8])
                linked_uuid = item["uuid"][:8]
                lines.append(f"  [dim]{desc:<{LW}}[/dim] {linked_title}  [dim]#{linked_uuid}[/dim]")

    # Fonto
    fonto = entry.get("fonto") or []
    if isinstance(fonto, str):
        fonto = [fonto]
    if fonto:
        lines.append(f"  [dim]{'fonto:':<{LW}}[/dim]")
        for src in fonto:
            if isinstance(src, dict):
                parts = [str(src[k]) for k in ("author", "aŭtoro", "autoro", "year", "jaro", "title", "titolo", "type", "tipo", "lingvo") if src.get(k)]
                lines.append(f"    {'; '.join(parts) if parts else str(src)}")
            elif src:
                lines.append(f"    {str(src)}")

    # Citajo
    citajo = entry.get("citajo") or []
    if isinstance(citajo, str):
        citajo = [citajo]
    if citajo:
        lines.append(f"  [dim]{'citajo:':<{LW}}[/dim]")
        for c in citajo:
            if isinstance(c, dict):
                text = str(c.get("teksto") or c.get("text") or "")
                author = str(c.get("author") or c.get("autoro") or c.get("auxtoro") or "")
                work = str(c.get("verko") or c.get("work") or "")
                year = str(c.get("jaro") or c.get("year") or "")
                parts = [f'"{text}"'] if text else []
                if author:
                    parts.append(author)
                if work:
                    parts.append(work)
                if year:
                    parts.append(year)
                lines.append(f"    {'; '.join(parts)}")
            elif c:
                lines.append(f"    {str(c)}")

    # Semantika
    semantika = entry.get("semantika") or []
    if isinstance(semantika, str):
        semantika = [semantika]
    if semantika:
        lines.append(f"  [dim]{'semantiko:':<{LW}}[/dim]")
        for item in (semantika if isinstance(semantika, list) else []):
            if isinstance(item, dict):
                arko = str(item.get("arko") or "")
                valoro = str(item.get("valoro") or "")
                unuo = str(item.get("unuo") or "")
                desc = _semantika_description(arko) or arko
                line = f"    {desc}: {valoro}"
                if unuo:
                    line += f" [{unuo}]"
                lines.append(line)

    # Datumo
    datumo = entry.get("datumo") or {}
    if isinstance(datumo, str):
        try:
            import json
            datumo = json.loads(datumo)
        except (json.JSONDecodeError, ValueError):
            datumo = {}
    if datumo:
        lines.append(f"  [dim]{'datumo:':<{LW}}[/dim]")
        for name in sorted(datumo.keys()):
            data_rows = datumo[name]
            row_count = len(data_rows) if isinstance(data_rows, list) else 1
            lines.append(f"    {name}: {row_count} {tr('vico(j)', 'row(s)')}")

    # Date stamps (if --cxio)
    if cxio:
        lines.append(f"  [dim]{'kreita:':<{LW}}[/dim] {(entry.get('kreita_je') or '')[:10]}")
        lines.append(f"  [dim]{'modifita:':<{LW}}[/dim] {(entry.get('modifita_je') or '')[:10]}")

    panel = Panel(
        "\n".join(lines),
        title=f"[bold]{render_markdown_text(title)}[/bold]",
        expand=False,
        border_style="dim",
    )
    console.print(panel)


__all__ = [
    "preferred_lang",
    "entry_locale_title",
    "normalize_lingvo_codes",
    "has_non_cli_renderable_markup",
    "render_markdown_text",
    "display_ligilo_items",
    "print_candidates_table",
    "copy_entry_reference",
    "browser_fallback_hint",
    "display_entry_panel",
    "_sem_rank",
    "_semantika_description",
]
