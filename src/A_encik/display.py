"""HTML display utilities for encik entries.

Uses A-core markdown_parser and markdown_html_view for rendering.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from A.core.markdown_parser import render_markdown
from A.core.markdown_html_view import preview_html
from A.utils.output import info


# Fields that contain Markdown and should be rendered as HTML
MARKDOWN_FIELDS = ["enhavo", "difinoj", "terminologio", "datumo", "noto"]

# Fields to display as-is (no markdown rendering)
PLAIN_FIELDS = ["uuid", "kreita_je", "modifita_je", "forigita_je"]


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

    # Render content fields
    for key, value in entry.items():
        if key in PLAIN_FIELDS:
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
        # Render as key-value list
        items = []
        for k, v in value.items():
            if v:
                items.append(f"<li><strong>{_escape_html(str(k))}</strong>: {_escape_html(str(v))}</li>")
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


__all__ = ["render_entry_html", "preview_entry", "MARKDOWN_FIELDS"]