"""Shared HTML rendering helpers for encik display.

Contains _render_field, _resolve_inline_links, _escape_html used
by both _display_entry.py (entry HTML) and display.py (facade).
"""

from __future__ import annotations

import re
from typing import Any

from A.core.markdown_parser import render_markdown

from A.core.markdown_html_view import preview_html


# Fields that contain Markdown and should be rendered as HTML
MARKDOWN_FIELDS = ["enhavo", "difinoj", "difinio", "terminologio", "datumo", "noto"]


def _render_field(key: str, value: Any, link_depth: int = 0) -> str:
    """Render a single field as HTML."""
    if value is None:
        return ""

    def _resolve(v: str) -> str:
        return _resolve_inline_links(v, link_depth=link_depth + 1) if v else v

    if isinstance(value, str):
        md_text = _resolve(value) if key in MARKDOWN_FIELDS else value
        if key in MARKDOWN_FIELDS:
            return f'<div class="field-content">{render_markdown(md_text)}</div>'
        else:
            return f'<div class="field-content">{_escape_html(value)}</div>'

    elif isinstance(value, dict):
        items = []
        use_markdown = key in MARKDOWN_FIELDS

        if key == "terminologio":
            groups: dict[str, list[str]] = {}
            for lang, term in value.items():
                term_str = str(term).strip() if term else ""
                if term_str:
                    groups.setdefault(term_str, []).append(lang)
            for term_str, langs in sorted(groups.items(),
                                          key=lambda x: x[1][0]):
                lang_label = "/".join(langs)
                t = _resolve(term_str) if use_markdown else term_str
                rendered = render_markdown(t) if use_markdown else _escape_html(term_str)
                items.append(f"<li><strong>{_escape_html(lang_label)}</strong>: {rendered}</li>")
        else:
            for k, v in value.items():
                if v:
                    if use_markdown and isinstance(v, str):
                        rendered = render_markdown(_resolve(v))
                    else:
                        rendered = _escape_html(str(v))
                    items.append(f"<li><strong>{_escape_html(str(k))}</strong>: {rendered}</li>")

        if items:
            return f'<div class="field-content"><ul>{"".join(items)}</ul></div>'
        return ""

    elif isinstance(value, list):
        items = []
        for v in value:
            if v:
                if isinstance(v, str) and key in MARKDOWN_FIELDS:
                    items.append(f"<li>{render_markdown(_resolve(v))}</li>")
                else:
                    items.append(f"<li>{_escape_html(str(v))}</li>")
        if items:
            return f'<div class="field-content"><ul>{"".join(items)}</ul></div>'
        return ""

    else:
        return f'<div class="field-content">{_escape_html(str(value))}</div>'


def _resolve_inline_links(md_text: str, link_depth: int = 0) -> str:
    """Resolve ``[label](#uuid, ...)`` inline links to clickable hyperlinks.

    The markdown parser (mistune) rejects URLs containing commas, so the
    autish-legacy format ``[Francio](#uuid, wdt:P17)`` is NOT rendered as
    a link. This function pre-processes the markdown text, resolving
    ``#uuid`` references to either:

    - A ``file://`` URL pointing to the target entry's HTML page (when
      *link_depth* > 0, i.e. inside a linked graph).
    - A plain ``[label](#uuid-prefix)`` markdown link (when
      *link_depth* == 0, i.e. single-entry view).

    Args:
        md_text: Markdown text containing ``[label](#uuid, ...)`` patterns.
        link_depth: Current link recursion depth. 0 = no recursion.

    Returns:
        Markdown text with resolved links.
    """
    from A_encik.service import get_service as _get_svc
    from A_encik.display_helpers import entry_locale_title as _elt
    from A_encik._display_entry import render_entry_html

    def _replace(m: re.Match) -> str:
        label = m.group(1).strip()
        ref_token = m.group(2).strip().split(",", 1)[0].strip().lstrip("#")
        if not ref_token or len(ref_token) < 8:
            return label
        svc = _get_svc()
        target = svc.get(ref_token)
        if not target:
            return f"{label} (#{ref_token[:8]})"
        short = target["uuid"][:8]
        if link_depth > 2:
            return f"[{label}](#{short})"
        if link_depth > 0:
            target_html = render_entry_html(target, include_fields=None, _link_depth=link_depth)
            _target_title = _elt(target) or "encik"
            target_path = preview_html(target_html, open_browser=False, title=_target_title)
            return f"[{label}](file://{target_path})"
        return f"[{label}](#{short})"

    return re.sub(
        r"\[([^\]]+)\]\(((?:#|ec#|vt#)[^)]+)\)",
        _replace,
        md_text,
    )


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


__all__ = [
    "_escape_html", "_render_field", "_resolve_inline_links",
    "MARKDOWN_FIELDS",
]
