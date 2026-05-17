"""HTML display utilities for encik entries.

Facade module — re-exports from split sub-modules for backward-compatible imports.
"""

from __future__ import annotations

from A_encik._display_html import (  # noqa: F401
    _escape_html, _render_field, _resolve_inline_links, MARKDOWN_FIELDS,
)
from A_encik._display_entry import (  # noqa: F401
    render_entry_html, preview_entry, maybe_auto_open_browser,
)
from A_encik._display_panel import display_entry_panel  # noqa: F401
from A.core.markdown_html_view import preview_html  # noqa: F401

# Fields used by other modules (kept here for backward compat)
PLAIN_FIELDS = ["uuid", "kreita_je", "modifita_je", "forigita_je"]
FIELD_SUPPRESSIONS = {"difinio": "difinoj"}

__all__ = [
    "_escape_html", "_render_field", "_resolve_inline_links",
    "render_entry_html", "preview_entry", "maybe_auto_open_browser",
    "display_entry_panel", "MARKDOWN_FIELDS",
]
