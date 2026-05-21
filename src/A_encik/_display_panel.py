"""Rich Panel display for encik entries (CLI output)."""

from __future__ import annotations

from typing import Any

from rich.panel import Panel

from A.console import console
from A import tr_multi
from A_encik.display_helpers import (
    preferred_lang,
    entry_locale_title,
    render_markdown_text,
    display_ligilo_items,
)


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

    enhavo = (entry.get("enhavo") or "").strip()
    if enhavo:
        lines.append(f"  [dim]{'enhavo:':<{LW}}[/dim]")
        for ln in enhavo.splitlines():
            ln_stripped = ln.strip()
            if ln_stripped:
                lines.append(f"    {render_markdown_text(ln_stripped)}")

    ligilo_items = display_ligilo_items(entry)
    if ligilo_items:
        for item in ligilo_items:
            tipo = item.get("tipo") or ""
            linked_title = item.get("titolo") or tr_multi("ne trovita", "not found", "non trouvé")
            if tipo == "ec#related":
                tipo_display = tr_multi("relaciita", "related", "lié")
            else:
                tipo_display = tipo[3:] if tipo.startswith("ec#") else tipo
            lines.append(f"  [dim]{tipo_display:<{LW-4}}[/dim] {linked_title}")

    fonto = entry.get("fonto") or []
    if isinstance(fonto, str):
        fonto = [fonto]
    if fonto:
        lines.append(f"  [dim]{'fonto:':<{LW}}[/dim]")
        for src in fonto:
            if isinstance(src, dict):
                parts = [str(src[k]) for k in ("author", "autoro", "year", "jaro", "title", "titolo", "type", "tipo", "lingvo") if src.get(k)]
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
        import re as _re
        parsed = []
        for _s_line in semantika.strip().split("\n"):
            _s_line = _s_line.strip()
            if not _s_line:
                continue
            m = _re.match(
                r'(str|int|float|bool)\s+(\S+)\s+(?:"([^"]*)"|(\S+))(?:\s+#(\S+))?',
                _s_line,
            )
            if m:
                _typ, _arc, _qv, _uv, _unit = m.groups()
                _val = _qv if _qv is not None else _uv
                _label = _arc
                _line = f"    {_label:<{LW-4}} {_val}"
                if _unit:
                    _line += f"  [{_unit}]"
                parsed.append(_line)
        if parsed:
            lines.append(f"  [dim]{'semantiko:':<{LW}}[/dim]")
            lines.extend(parsed)
    elif semantika:
        lines.append(f"  [dim]{'semantiko:':<{LW}}[/dim]")
        for item in (semantika if isinstance(semantika, list) else []):
            if isinstance(item, dict):
                arko = str(item.get("arko") or "")
                valoro = str(item.get("valoro") or "")
                unuo = str(item.get("unuo") or "")
                _label = arko
                _line = f"    {_label:<{LW-4}} {valoro}"
                if unuo:
                    _line += f"  [{unuo}]"
                lines.append(_line)

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
    )
    console.print(panel)


__all__ = ["display_entry_panel"]
