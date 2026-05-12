"""HTML display utilities for encik entries.

Uses A-core markdown_parser and markdown_html_view for rendering.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from A.core.markdown_parser import render_markdown
from A.core.markdown_html_view import preview_html
from A.utils.output import info


# Fields that contain Markdown and should be rendered as HTML
MARKDOWN_FIELDS = ["enhavo", "difinoj", "difinio", "terminologio", "datumo", "noto"]

# Fields to display as-is (no markdown rendering)
PLAIN_FIELDS = ["uuid", "kreita_je", "modifita_je", "forigita_je"]

# Fields already rendered in the header (skip during field iteration)
SKIP_FIELDS = {"titolo"}

# Fields suppressed when a richer alternative exists
FIELD_SUPPRESSIONS = {
    "difinio": "difinoj",  # Skip singular difinio when plural difinoj is non-empty
}


def render_entry_html(
    entry: dict[str, Any],
    include_fields: list[str] | None = None,
) -> str:
    """Render an encik entry as an HTML page.

    Args:
        entry: The entry dictionary
        include_fields: Optional list of fields to include (default: all)

    Returns:
        HTML string with rendered markdown fields
    """
    title = entry.get("titolo", entry.get("uuid", "Unkonata"))
    created = entry.get("kreita_je", "")
    modified = entry.get("modifita_je", "")

    # Build field rows
    rows = []

    # Metadata header
    rows.append(f"<h1>{_escape_html(str(title))}</h1>")
    if created:
        rows.append(f'<p class="meta">Kreita: {created[:19]}</p>')
    if modified:
        rows.append(f'<p class="meta">Modifita: {modified[:19]}</p>')

    # Render content fields (skip header fields and suppressions)
    for key, value in entry.items():
        if key in PLAIN_FIELDS:
            continue
        if key in SKIP_FIELDS:
            continue
        if key in FIELD_SUPPRESSIONS:
            richer = FIELD_SUPPRESSIONS[key]
            if entry.get(richer):  # dict/list — truthy check
                continue
        if include_fields and key not in include_fields:
            continue

        field_html = _render_field(key, value)
        if field_html:
            rows.append(f'<div class="field"><label>{key}</label>{field_html}</div>')

    # Build complete HTML document
    html = f"""<!DOCTYPE html>
<html lang="eo">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_escape_html(str(title))}</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #333; }}
        .meta {{ color: #666; font-size: 0.9em; }}
        .field {{ margin: 20px 0; }}
        .field label {{ display: block; font-weight: bold; color: #555; margin-bottom: 5px; }}
        .field-content {{ padding: 10px; background: #f9f9f9; border-radius: 5px; }}
        pre {{ background: #eee; padding: 10px; overflow-x: auto; }}
        code {{ background: #eee; padding: 2px 5px; }}
    </style>
</head>
<body>
    {''.join(rows)}
</body>
</html>"""

    return html


def _render_field(key: str, value: Any) -> str:
    """Render a single field as HTML."""
    if value is None:
        return ""

    # Handle different field types
    if isinstance(value, str):
        if key in MARKDOWN_FIELDS:
            # Render markdown
            return f'<div class="field-content">{render_markdown(value)}</div>'
        else:
            # Plain text
            return f'<div class="field-content">{_escape_html(value)}</div>'

    elif isinstance(value, dict):
        # Render as key-value list, rendering markdown for MARKDOWN_FIELDS
        items = []
        use_markdown = key in MARKDOWN_FIELDS

        if key == "terminologio":
            # Group identical terms across languages: {term: [langs...]}
            groups: dict[str, list[str]] = {}
            for lang, term in value.items():
                term_str = str(term).strip() if term else ""
                if term_str:
                    groups.setdefault(term_str, []).append(lang)
            for term_str, langs in sorted(groups.items(),
                                          key=lambda x: x[1][0]):  # sort by first lang
                lang_label = "/".join(langs)
                rendered = render_markdown(term_str) if use_markdown else _escape_html(term_str)
                items.append(f"<li><strong>{_escape_html(lang_label)}</strong>: {rendered}</li>")
        else:
            for k, v in value.items():
                if v:
                    if use_markdown and isinstance(v, str):
                        rendered = render_markdown(v)
                    else:
                        rendered = _escape_html(str(v))
                    items.append(f"<li><strong>{_escape_html(str(k))}</strong>: {rendered}</li>")

        if items:
            return f'<div class="field-content"><ul>{"".join(items)}</ul></div>'
        return ""

    elif isinstance(value, list):
        # Render as list
        items = [_escape_html(str(v)) for v in value if v]
        if items:
            return f'<div class="field-content"><ul>{"".join(f"<li>{i}</li>" for i in items)}</ul></div>'
        return ""

    else:
        return f'<div class="field-content">{_escape_html(str(value))}</div>'


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def preview_entry(
    entry: dict[str, Any],
    open_browser: bool = True,
    title: str | None = None,
) -> Path:
    """Render and preview an entry in browser.

    Args:
        entry: The entry dictionary
        open_browser: If True, open in browser
        title: Optional title override

    Returns:
        Path to the rendered HTML file
    """
    html = render_entry_html(entry)
    title = title or entry.get("titolo", "encik")
    return preview_html(html, open_browser=open_browser, title=title)


def maybe_auto_open_browser(entry: dict[str, Any]) -> bool:
    """Auto-open entry in browser if it contains KaTeX/images.

    Checks markdown fields for non-CLI-renderable markup.
    Respects ``A_ENCIK_DISABLE_BROWSER_AUTO_OPEN`` env var to opt out.

    Returns True if browser was opened (caller should return early), False otherwise.
    """
    if os.environ.get("A_ENCIK_DISABLE_BROWSER_AUTO_OPEN"):
        return False

    from A import tr_multi
    from A_encik.display_helpers import has_non_cli_renderable_markup

    entry_body = " ".join(
        filter(None, [
            entry.get("enhavo", "") or "",
            entry.get("difinio", "") or "",
            *((entry.get("difinoj") or {}).values()),
        ])
    )
    if not has_non_cli_renderable_markup(entry_body):
        return False

    preview_entry(entry, open_browser=True)
    info(tr_multi(
        "Malfermis en retumilo por KaTeX/bildoj",
        "Opened in browser for KaTeX/images",
        "Ouvert dans le navigateur pour KaTeX/images",
    ))
    return True


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

    from A.console import console
    from A import tr_multi
    from A_encik.display_helpers import (
        preferred_lang,
        entry_locale_title,
        render_markdown_text,
        display_ligilo_items,
        _sem_rank,
        _semantika_description,
    )

    terminologio = entry.get("terminologio") or {}
    difinoj = entry.get("difinoj") or {}
    if not selected_lang:
        selected_lang = preferred_lang(terminologio, difinoj)
    title = entry_locale_title(entry, [selected_lang] if selected_lang else None)

    lines: list[str] = []
    LW = 14

    lines.append(f"  [dim]{'uuid:':<{LW}}[/dim] {entry.get('uuid', '')[:8]}")
    lines.append(f"  [dim]{'lingvo:':<{LW}}[/dim] {selected_lang or '-'}")

    if cxio and terminologio:
        lines.append(f"  [dim]{'terminologio:':<{LW}}[/dim]")
        for lang, term in sorted(terminologio.items()):
            lines.append(f"    {lang}: {render_markdown_text(term)}")

    difinio = (
        difinoj.get(selected_lang)
        or entry.get("difinio", "")
        or next(iter(difinoj.values()), "")
    ).strip()
    if difinio:
        lines.append(f"  [dim]{'difino:':<{LW}}[/dim]")
        for ln in difinio.splitlines():
            lines.append(f"    {render_markdown_text(ln)}")

    if cxio and difinoj:
        lines.append(f"  [dim]{'difinoj:':<{LW}}[/dim]")
        for lang, term_def in sorted(difinoj.items()):
            lines.append(f"    {lang}: {render_markdown_text(term_def)}")

    enhavo = (entry.get("enhavo") or "").strip()
    if enhavo and cxio:
        lines.append(f"  [dim]{'enhavo:':<{LW}}[/dim]")
        for ln in enhavo.splitlines():
            ln_stripped = ln.strip()
            if ln_stripped:
                lines.append(f"    {render_markdown_text(ln_stripped)}")

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
                linked_title = item.get("titolo") or tr_multi("ne trovita", "not found", "non trouvé")
                linked_uuid = item["uuid"][:8]
                lines.append(f"  [dim]{desc:<{LW}}[/dim] {linked_title}  [dim]#{linked_uuid}[/dim]")

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

    datumo = entry.get("datumo") or {}
    if isinstance(datumo, str):
        try:
            import json
            datumo = json.loads(datumo)
        except (json.JSONDecodeError, ValueError):
            datumo = {}
    if datumo:
        lines.append(f"  [dim]{'datumo:':<{LW}}[/dim]")
        for name in sorted(k for k in datumo if not k.startswith("_")):
            data_rows = datumo[name]
            row_count = len(data_rows) if isinstance(data_rows, list) else 1
            lines.append(f"    {name}: {row_count} {tr_multi('vico(j)', 'row(s)')}")

    if cxio:
        lines.append(f"  [dim]{'kreita:':<{LW}}[/dim] {(entry.get('kreita_je') or '')[:10]}")
        lines.append(f"  [dim]{'modifita:':<{LW}}[/dim] {(entry.get('modifita_je') or '')[:10]}")

    panel_title_text = render_markdown_text(title)
    max_title_w = console.width - 6
    if len(panel_title_text) > max_title_w:
        panel_title_text = panel_title_text[:max_title_w] + "…"
    panel = Panel(
        "\n".join(lines),
        title=f"[bold]{panel_title_text}[/bold]",
        expand=False,
        border_style="dim",
    )
    console.print(panel)


__all__ = ["render_entry_html", "preview_entry", "maybe_auto_open_browser", "display_entry_panel", "MARKDOWN_FIELDS"]