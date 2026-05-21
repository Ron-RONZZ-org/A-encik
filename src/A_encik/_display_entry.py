"""Entry HTML rendering — single entry view page."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from A.core.markdown_html_view import preview_html, KATEX_HTML

from A import tr_multi
from A.utils.output import info

from A_encik._display_html import (
    _escape_html, _render_field, _resolve_inline_links,
    MARKDOWN_FIELDS,
)


# Fields to display as-is (no markdown rendering)
PLAIN_FIELDS = {"uuid", "kreita_je", "modifita_je", "forigita_je"}

# Fields already rendered in the header (skip during field iteration).
# "titolo" here is the dict key populated by row_to_dict from terminologio,
# not a DB column.
SKIP_FIELDS = {"titolo"}

# Internal/technical fields never shown to users (ranking, search, etc.)
INTERNAL_FIELDS = {
    "_title_prefix", "_frequency", "_compactness",
    "terminologio_search", "titolo_fold",
}

# Fields suppressed when a richer alternative exists
FIELD_SUPPRESSIONS = {
    "difinio": "difinoj",  # Skip singular difinio when plural difinoj is non-empty
}

# User-facing display order — matches user expectation:
#   terminologio (title) → difino (definition) → semantika (data) →
#   ligilo (links) → fonto → citajo → datumo
DISPLAY_FIELD_ORDER = [
    "terminologio",
    "difinoj",
    "difinio",   # only shown if difinoj empty (via FIELD_SUPPRESSIONS)
    "semantika",
    "ligilo",
    "enhavo",
    "fonto",
    "citajo",
    "datumo",
]


def render_entry_html(
    entry: dict[str, Any],
    include_fields: list[str] | None = None,
    _link_depth: int = 0,
) -> str:
    """Render an encik entry as an HTML page.

    Args:
        entry: The entry dictionary
        include_fields: Optional list of fields to include (default: all)

    Returns:
        HTML string with rendered markdown fields
    """
    from A_encik.display_helpers import display_ligilo_items, entry_locale_title

    title = entry_locale_title(entry) or entry.get("uuid", "Unkonata")
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

    # Ordered field rendering — follows DISPLAY_FIELD_ORDER for predictable
    # user-facing arrangement. Special rendering for semantika and ligilo.
    rendered_keys: set[str] = set()

    for key in DISPLAY_FIELD_ORDER:
        rendered_keys.add(key)

        # Filter by include_fields if specified
        if include_fields is not None and key not in include_fields:
            continue

        # -- Suppression: skip singular difinio when difinoj is present --
        if key in FIELD_SUPPRESSIONS:
            richer = FIELD_SUPPRESSIONS[key]
            if entry.get(richer):
                continue

        # -- Semantika: custom string format → arc/value lines --
        if key == "semantika":
            sem_raw = entry.get("semantika") or ""
            if isinstance(sem_raw, str) and sem_raw.strip() and sem_raw != "[]":
                import re as _re
                sem_rows: list[str] = []
                for _s_line in sem_raw.strip().split("\n"):
                    _s_line = _s_line.strip()
                    if not _s_line:
                        continue
                    m = _re.match(
                        r'(str|int|float|bool)\s+(\S+)\s+(?:"([^"]*)"|(\S+))(?:\s+#(\S+))?',
                        _s_line,
                    )
                    if m:
                        _typ, _arc, _qv, _uv, _unit = m.groups()
                        _val = _escape_html(_qv if _qv is not None else _uv)
                        _line = f"<li><code>{_escape_html(_arc)}</code> {_val}</li>"
                        sem_rows.append(_line)
                if sem_rows:
                    rows.append(f'<div class="field"><label>semantiko</label><div class="field-content"><ul>{"".join(sem_rows)}</ul></div></div>')
            continue

        # -- Ligilo: show as {tipo} {target entry} --
        if key == "ligilo":
            lig_raw = entry.get("ligilo") or []
            if isinstance(lig_raw, list):
                from A_encik.display_helpers import display_ligilo_items
                _lig_items = display_ligilo_items(entry)
                if _lig_items:
                    lig_rows = [
                        f"<li><span class=\"tipo\">{_escape_html(it['tipo'] or '')}</span> {_escape_html(it.get('titolo', '') or '')}  <span class=\"uuid\">#{_escape_html(it['uuid'][:8])}</span></li>"
                        for it in _lig_items
                    ]
                    rows.append(f'<div class="field"><label>ligilo</label><div class="field-content"><ul>{"".join(lig_rows)}</ul></div></div>')
            continue

        # -- General field rendering --
        value = entry.get(key)
        if value is None:
            continue

        # Skip empty string values
        if isinstance(value, str) and not value:
            continue

        # Resolve inline semantic arcs before markdown rendering.
        if isinstance(value, str) and key not in PLAIN_FIELDS:
            value = _resolve_inline_links(value, link_depth=_link_depth + 1)

        field_html = _render_field(key, value, link_depth=_link_depth)
        if field_html:
            rows.append(f'<div class="field"><label>{key}</label>{field_html}</div>')

    # Fallback: render any unknown keys (from plugins, extensions, etc.)
    # that are not in any reserved set.
    _reserved = PLAIN_FIELDS | SKIP_FIELDS | INTERNAL_FIELDS | rendered_keys
    for key, value in entry.items():
        if key in _reserved:
            continue
        if include_fields is not None and key not in include_fields:
            continue
        if isinstance(value, str) and not value:
            continue
        field_html = _render_field(key, value, link_depth=_link_depth)
        if field_html:
            rows.append(f'<div class="field field-extended"><label>{key}</label>{field_html}</div>')

    # Build complete HTML document
    html = f"""<!DOCTYPE html>
<html lang="eo">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_escape_html(str(title))}</title>
    {KATEX_HTML()}
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #333; }}
        .meta {{ color: #666; font-size: 0.9em; }}
        .field {{ margin: 20px 0; }}
        .field label {{ display: block; font-weight: bold; color: #555; margin-bottom: 5px; }}
        .field-content {{ padding: 10px; background: #f9f9f9; border-radius: 5px; }}
        pre {{ background: #eee; padding: 10px; overflow-x: auto; }}
        code {{ background: #eee; padding: 2px 5px; }}
        .tipo {{ color: #888; font-size: 0.85em; }}
        .uuid {{ color: #aaa; font-size: 0.8em; }}
    </style>
</head>
<body>
    {''.join(rows)}
</body>
</html>"""

    return html


def preview_entry(
    entry: dict[str, Any],
    open_browser: bool = True,
    title: str | None = None,
) -> Path:
    """Render and preview an entry in browser.

    The browser tab title comes from ``preview_html`` → ``_generate_html_wrapper``
    which wraps the HTML in a full page with its own ``<title>``.
    Must be locale-aware or the browser tab will show the wrong language.

    Args:
        entry: The entry dictionary
        open_browser: If True, open in browser
        title: Optional title override (locale-aware)

    Returns:
        Path to the rendered HTML file
    """
    from A_encik.display_helpers import entry_locale_title as _elt

    html = render_entry_html(entry, _link_depth=0)
    if not title:
        title = _elt(entry) or "encik"
    return preview_html(html, open_browser=open_browser, title=title)


def maybe_auto_open_browser(entry: dict[str, Any]) -> bool:
    """Auto-open entry in browser if it contains KaTeX/images.

    Checks markdown fields for non-CLI-renderable markup.
    Respects ``A_ENCIK_DISABLE_BROWSER_AUTO_OPEN`` env var to opt out.

    Returns True if browser was opened (caller should return early), False otherwise.
    """
    if os.environ.get("A_ENCIK_DISABLE_BROWSER_AUTO_OPEN"):
        return False

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

    path = preview_entry(entry)
    info(tr_multi(
        f"HTML antaŭrigardo preta: file://{path}",
        f"HTML preview ready: file://{path}",
        f"Aperçu HTML prêt: file://{path}",
    ))
    return True


__all__ = [
    "render_entry_html", "preview_entry", "maybe_auto_open_browser",
    "MARKDOWN_FIELDS",
]
