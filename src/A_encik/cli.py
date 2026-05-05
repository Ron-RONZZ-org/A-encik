"""CLI for encik command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from A import error, info, copy_to_clipboard
from A.console import console
from A import tr_multi
from A.utils.interactive import select_candidate

from A_encik.service import get_service
from A_encik.display_helpers import (
    preferred_lang,
    entry_locale_title,
    render_markdown_text,
    has_non_cli_renderable_markup,
    display_ligilo_items,
    normalize_lingvo_codes,
    print_candidates_table,
    copy_entry_reference,
    browser_fallback_hint,
    display_entry_panel,
)

app = typer.Typer(
    name="encik",
    help=tr_multi("Encik — microapplication de gestion de connaissances.", "Encik — persona sci-mastruma mikroapo.", "Encik — persona sci-mastruma mikroapo."),
    no_args_is_help=False,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)


@app.command("ls")
def ls(
    pagho: int = typer.Option(
        1,
        "-p",
        "--pagho",
        help=tr_multi("Numero de paĝo", "Page number (1-indexed)", "Numéro de page (indexé à partir de 1)"),
        min=1,
    ),
    inversa: bool = typer.Option(
        False,
        "-i",
        "--inversa",
        help=tr_multi("Listi de la plej malnova anstataŭ la plej nova", "List from oldest instead of newest", "Lister du plus ancien au plus récent"),
    ),
    per_pagho: int = typer.Option(
        10,
        "--per-pagho",
        help=tr_multi("Nombro de eniroj po paĝo", "Number of entries per page", "Nombre d'entrées par page"),
        min=1,
        max=100,
    ),
) -> None:
    """List encik entries with pagination.

    By default, shows the newest 10 entries. Use -p to paginate and -i to reverse order.
    """
    service = get_service()
    total = service.count()

    if total == 0:
        info(tr("Neniu eniro en la datumbazo.", "No entries in the database.", "Aucune entrée dans la base."))
        return

    offset = (pagho - 1) * per_pagho
    total_pages = (total + per_pagho - 1) // per_pagho

    if offset >= total:
        error(tr(
            f"Paĝo {pagho} ne ekzistas (nur {total_pages} paĝo(j)).",
            f"Page {pagho} does not exist (only {total_pages} page(s)).",
        ))
        raise typer.Exit(1)

    entries = service.list(order_by="kreita_je", desc=not inversa, limit=per_pagho, offset=offset)

    # Pagination summary
    start = offset + 1
    end = min(offset + per_pagho, total)
    console.print(f"[dim]{tr('Montras', 'Showing')} {start}-{end} {tr('el', 'of')} {total} {tr('eniro(j)', 'entry(ies)')} | {tr('Paĝo', 'Page')} {pagho}/{total_pages}[/dim]")

    # Table
    table = Table(show_header=True, header_style="dim", border_style="dim", expand=False)
    table.add_column("UUID", style="dim", width=10, no_wrap=True)
    table.add_column(tr("Titolo", "Title"), min_width=30)
    table.add_column(tr("Kreita", "Created"), width=12)
    table.add_column(tr("Modifita", "Modified"), width=12)

    for e in entries:
        uid_short = e.get("uuid", "")[:8]
        titolo = entry_locale_title(e)
        kreita = (e.get("kreita_je") or "")[:10]
        modifita = (e.get("modifita_je") or "")[:10]
        table.add_row(uid_short, titolo, kreita, modifita)

    console.print(table)


@app.command("vidi")
def vidi(
    ref: str = typer.Argument(
        ...,
        help=tr_multi("UUID aŭ titolo", "UUID or title", "UUID ou titre"),
    ),
    lingvo: Optional[str] = typer.Option(
        None,
        "-l",
        "--lingvo",
        help=tr_multi("Kodo de lingvo", "Language code", "Code de langue"),
    ),
    cxio: bool = typer.Option(
        False,
        "-a",
        "--cxio",
        help=tr_multi("Montri ĉiujn disponeblajn lingvojn kaj kampojn", "Show all available languages and fields", "Afficher toutes les langues et champs disponibles"),
    ),
    html: bool = typer.Option(
        False,
        "-H",
        "--html",
        help=tr_multi("Montri kiel HTML", "Render as HTML", "Afficher en HTML"),
    ),
    open_browser: bool = typer.Option(
        False,
        "-o",
        "--open",
        help=tr_multi("Malfermi en retumilo", "Open in browser", "Ouvrir dans le navigateur"),
    ),
    kopii: bool = typer.Option(
        False,
        "-k",
        "--kopii",
        help=tr_multi("Kopii #uuid al tondujo", "Copy #uuid to clipboard", "Copier #uuid dans le presse-papier"),
    ),
    semantika_kopii: bool = typer.Option(
        False,
        "-sk",
        "--semantika-kopii",
        help=tr_multi("Kopii [titolo](#uuid) al tondujo", "Copy [titolo](#uuid) to clipboard", "Copier [titolo](#uuid) dans le presse-papier"),
    ),
) -> None:
    """View a knowledge entry."""
    service = get_service()

    # Try UUID first
    entry = service.get(ref)

    # Try title if not found
    if not entry:
        entry = service.find_by_titolo(ref)

    # Try UUID prefix if not found
    if not entry:
        matches = service.find_by_uuid_prefix(ref)
        if len(matches) == 1:
            entry = matches[0]

    if not entry:
        error(tr(f"Encik {ref} ne trovitas", f"Entry {ref} not found", f"Entree {ref} non trouve"))
        raise typer.Exit(1)

    # HTML rendering
    if html or open_browser:
        from A_encik.display import preview_entry
        preview_entry(entry, open_browser=open_browser)
        if open_browser:
            info(tr("Malfermis en retumilo", "Opened in browser", "Ouvert dans le navigateur"))
        return

    # Handle clipboard before display
    if kopii or semantika_kopii:
        copy_entry_reference(entry, semantika=semantika_kopii)

    # Display entry as Rich Panel
    selected_lang = (lingvo or "").strip().lower() or preferred_lang(
        entry.get("terminologio") or {}, entry.get("difinoj") or {}
    )
    display_entry_panel(entry, selected_lang=selected_lang, cxio=cxio)


@app.command("aldoni")
def aldoni(
    titolo: str = typer.Argument(..., help=tr_multi("Titolo", "Title", "Title")),
    difinio: Optional[str] = typer.Option(None, "-d", "--difino", help=tr_multi("Difino", "Definition", "Definition")),
    enhavo: Optional[str] = typer.Option(None, "-e", "--enhavo", help=tr_multi("Enhavo", "Content", "Content")),
    terminologio: Optional[str] = typer.Option(None, "-t", "--terminologio", help=tr_multi("Terminologio (JSON)", "Terminology (JSON)", "Terminologie (JSON)")),
    superklaso: Optional[str] = typer.Option(None, "-s", "--superklaso", help=tr_multi("Superklaso UUIDoj (JSON)", "Superclass UUIDs (JSON)", "UUIDs de superclasse (JSON)")),
    ligilo: Optional[str] = typer.Option(None, "-l", "--ligilo", help=tr_multi("Ligiloj (JSON)", "Links (JSON)", "Liens (JSON)")),
    fonto: Optional[str] = typer.Option(None, "-f", "--fonto", help=tr_multi("Fontoj (JSON)", "Sources (JSON)", "Sources (JSON)")),
    kopii: bool = typer.Option(
        False,
        "-k",
        "--kopii",
        help=tr_multi("Kopii #uuid al tondujo", "Copy #uuid to clipboard", "Copier #uuid dans le presse-papier"),
    ),
    semantika_kopii: bool = typer.Option(
        False,
        "-sk",
        "--semantika-kopii",
        help=tr_multi("Kopii [titolo](#uuid) al tondujo", "Copy [titolo](#uuid) to clipboard", "Copier [titolo](#uuid) dans le presse-papier"),
    ),
) -> None:
    """Add a new knowledge entry."""
    import json
    
    service = get_service()
    
    data: dict = {"titolo": titolo}
    if difinio:
        data["difinio"] = difinio
    if enhavo:
        data["enhavo"] = enhavo
    
    # Parse JSON fields
    if terminologio:
        try:
            data["terminologio"] = json.loads(terminologio)
        except json.JSONDecodeError:
            error(tr("Nevalida JSON por terminologio", "Invalid JSON for terminologio", "JSON nevalida por terminologio"))
            raise typer.Exit(1)
    else:
        data["terminologio"] = {"eo": titolo}
    
    if superklaso:
        try:
            data["superklaso"] = json.loads(superklaso)
        except json.JSONDecodeError:
            error(tr("Nevalida JSON por superklaso", "Invalid JSON for superklaso", "JSON nevalida por superklaso"))
            raise typer.Exit(1)
    
    if ligilo:
        try:
            data["ligilo"] = json.loads(ligilo)
        except json.JSONDecodeError:
            error(tr("Nevalida JSON por ligilo", "Invalid JSON for ligilo", "JSON nevalida por ligilo"))
            raise typer.Exit(1)
    
    if fonto:
        try:
            data["fonto"] = json.loads(fonto)
        except json.JSONDecodeError:
            error(tr("Nevalida JSON por fonto", "Invalid JSON for fonto", "JSON nevalida por fonto"))
            raise typer.Exit(1)
    
    entry = service.create(data)
    info(tr(f"Aldonis {titolo}", f"Added {titolo}", f"Ajoute {titolo}"))
    console.print(f"[green]UUID:[/] {entry.get('uuid')}")
    
    # Handle clipboard copy options
    if kopii or semantika_kopii:
        if kopii:
            copy_to_clipboard(f"#{entry['uuid'][:8]}")
        if semantika_kopii:
            copy_to_clipboard(f"[{entry['titolo']}](#{entry['uuid'][:8]})")


@app.command("modifi")
def modifi(
    ref: str = typer.Argument(
        ...,
        help=tr_multi("UUID aŭ titolo", "UUID or title", "UUID ou titre"),
    ),
    titolo: Optional[str] = typer.Option(None, "-t", "--titolo", help=tr_multi("Nova titolo", "New title", "New title")),
    difinio: Optional[str] = typer.Option(None, "-d", "--difino", help=tr_multi("Nova difino", "New definition", "New definition")),
    enhavo: Optional[str] = typer.Option(None, "-e", "--enhavo", help=tr_multi("Nova enhavo", "New content", "New content")),
    kopii: bool = typer.Option(
        False,
        "-k",
        "--kopii",
        help=tr_multi("Kopii #uuid al tondujo", "Copy #uuid to clipboard", "Copier #uuid dans le presse-papier"),
    ),
    semantika_kopii: bool = typer.Option(
        False,
        "-sk",
        "--semantika-kopii",
        help=tr_multi("Kopii [titolo](#uuid) al tondujo", "Copy [titolo](#uuid) to clipboard", "Copier [titolo](#uuid) dans le presse-papier"),
    ),
) -> None:
    """Modify a knowledge entry."""
    service = get_service()
    
    # Find entry
    entry = service.get(ref)
    if not entry:
        entry = service.find_by_titolo(ref)
    if not entry:
        matches = service.find_by_uuid_prefix(ref)
        if matches:
            if len(matches) == 1:
                entry = matches[0]
            else:
                error(tr("Uz pli specifan referencon", "Use a more specific reference", "Uz pli specifan referencon"))
                raise typer.Exit(1)
    
    if not entry:
        error(tr(f"Encik {ref} ne trovitas", f"Entry {ref} not found", f"Entree {ref} non trouve"))
        raise typer.Exit(1)
    
    # Build update data
    data = {}
    if titolo:
        data["titolo"] = titolo
    if difinio is not None:
        data["difinio"] = difinio
    if enhavo is not None:
        data["enhavo"] = enhavo
    
    if not data:
        info(tr("Neniuj sxangoj", "No changes", "Aucun changement"))
        return
    
    updated = service.update(entry["uuid"], data)
    info(tr(f"Modifikis {updated['titolo']}", f"Modified {updated['titolo']}", f"Modifie {updated['titolo']}"))
    
    # Handle clipboard copy options
    if kopii or semantika_kopii:
        if kopii:
            copy_to_clipboard(f"#{updated['uuid'][:8]}")
        if semantika_kopii:
            copy_to_clipboard(f"[{updated['titolo']}](#{updated['uuid'][:8]})")


@app.command("forigi")
def forigi(
    ref: str = typer.Argument(
        ...,
        help=tr_multi("UUID aŭ titolo", "UUID or title", "UUID ou titre"),
    ),
    hard: bool = typer.Option(
        False,
        "--hard",
        "-H",
        help=tr_multi("Suppression permanente", "Permanent delete (no trash)", "Suppression définitive (pas de corbeille)"),
    ),
) -> None:
    """Delete a knowledge entry."""
    service = get_service()
    
    # Find entry
    entry = service.get(ref)
    if not entry:
        entry = service.find_by_titolo(ref)
    if not entry:
        matches = service.find_by_uuid_prefix(ref)
        if matches:
            if len(matches) == 1:
                entry = matches[0]
            else:
                error(tr("Uz pli specifan referencon", "Use a more specific reference", "Uz pli specifan referencon"))
                raise typer.Exit(1)
    
    if not entry:
        error(tr(f"Encik {ref} ne trovitas", f"Entry {ref} not found", f"Entree {ref} non trouve"))
        raise typer.Exit(1)
    
    uuid = entry["uuid"]
    soft = not hard
    service.delete(uuid, soft=soft)
    
    if soft:
        info(tr(f"Forigis {entry['titolo']} (sxoveblas)", f"Deleted {entry['titolo']} (soft)", f"Supprime {entry['titolo']} ( mou)"))
    else:
        info(tr(f"Forigis {entry['titolo']} (permanenta)", f"Deleted {entry['titolo']} (permanent)", f"Supprime {entry['titolo']} (permanent)"))


@app.command("serci")
def serci(
    demando: str | None = typer.Argument(
        None,
        help=tr_multi("Serĉa demando (titolo defaŭlte, plena teksto kun -t)", "Search query (title by default, full text with -t)", "Requête de recherche (titre par défaut, texte intégral avec -t)"),
    ),
    lingvo: str | None = typer.Option(
        None,
        "-l",
        "--lingvo",
        help=tr_multi("Preferataj lingvokodoj (komo-disigitaj). Ekz: -l fr,en", "Preferred language codes (comma-separated). Example: -l fr,en", "Codes de langue préférés (séparés par des virgules). Exemple: -l fr,en"),
    ),
    teksto: bool = typer.Option(
        False,
        "-t",
        "--teksto",
        help=tr_multi("Serĉi plenan enhavon (ne nur titolo)", "Search full content (not just title)", "Rechercher dans tout le contenu (pas seulement le titre)"),
    ),
    preciza: bool = typer.Option(
        False,
        "-p",
        "--preciza",
        help=tr_multi("Malŝalti malklaran rezervan kongruigon", "Disable fuzzy fallback matching", "Disable fuzzy fallback matching"),
    ),
    nova_unue: bool = typer.Option(
        False,
        "--nova-unue",
        help=tr_multi("Plej novaj rezultoj unue", "Newest results first", "Newest results first"),
    ),
    malnova_unue: bool = typer.Option(
        False,
        "--malnova-unue",
        help=tr_multi("Plej malnovaj rezultoj unue", "Oldest results first", "Oldest results first"),
    ),
    subklasoj: str | None = typer.Option(
        None,
        "-s",
        "--subklasoj",
        help=tr_multi("Serĉi subklasojn de termino (titolo aŭ UUID)", "Search subclasses of term (title or UUID)", "Rechercher les sous-classes d'un terme (titre ou UUID)"),
    ),
    superklasoj: str | None = typer.Option(
        None,
        "-S",
        "--superklasoj",
        help=tr_multi("Serĉi superklasojn de termino (titolo aŭ UUID)", "Search superclasses of term (title or UUID)", "Rechercher les super-classes d'un terme (titre ou UUID)"),
    ),
    limo: int = typer.Option(
        10,
        "-L",
        "--limo",
        help=tr_multi("Maksimumaj rezultoj (defaŭlte 10)", "Max results (default 10)", "Résultats max (10 par défaut)"),
    ),
    html: bool = typer.Option(
        False,
        "-H",
        "--html",
        help=tr_multi("Montri kiel semantikan retan diagramon en retumilo", "Display results as semantic web diagram in browser", "Display results as semantic web diagram in browser"),
    ),
    kopii: bool = typer.Option(
        False,
        "-k",
        "--kopii",
        help=tr_multi("Kopii #uuid al tondujo", "Copy #uuid to clipboard", "Copier #uuid dans le presse-papier"),
    ),
    semantika_kopii: bool = typer.Option(
        False,
        "-sk",
        "--semantika-kopii",
        help=tr_multi("Kopii [titolo](#uuid) al tondujo", "Copy [titolo](#uuid) to clipboard", "Copier [titolo](#uuid) dans le presse-papier"),
    ),
) -> None:
    """Search knowledge entries."""
    service = get_service()
    
    # Handle clipboard validation
    if kopii and semantika_kopii:
        error(tr("Use only one of --kopii or --semantika-kopii", "Use only one of --kopii or --semantika-kopii", "Uzu nur unu el --kopii aŭ --semantika-kopii"))
        raise typer.Exit(1)
    
    # Parse preferred search languages
    preferred_search_langs = normalize_lingvo_codes(lingvo)

    def _preferred_search_lang(entry: dict) -> str:
        """Get best language for a single entry."""
        if preferred_search_langs:
            for lang in preferred_search_langs:
                if entry.get("terminologio", {}).get(lang) and entry.get("difinoj", {}).get(lang):
                    return lang
        return preferred_lang(entry.get("terminologio", {}), entry.get("difinoj", {}))

    def _copy_and_show(candidates: list[dict], idx: int = 0) -> None:
        """Copy reference and display a single entry."""
        if not candidates or idx >= len(candidates):
            return
        target = candidates[idx]
        if kopii or semantika_kopii:
            copy_entry_reference(target, semantika=semantika_kopii)
        display_entry_panel(target, selected_lang=_preferred_search_lang(target))

    # No query - list all up to limo
    if demando is None:
        entries = service.list(order_by="kreita_je", desc=True, limit=limo)
        if not entries:
            info(tr("Neniuj rezultoj", "No results", "Aucun resultat"))
            return
        print_candidates_table(entries, preferred_langs=preferred_search_langs)
        info(tr(f"{len(entries)} rezultoj", f"{len(entries)} results", f"{len(entries)} resultats"))
        return

    # Resolve the root entry first
    entry = service.get(demando)
    if not entry:
        entry = service.find_by_titolo(demando)
    if not entry:
        matches = service.find_by_uuid_prefix(demando)
        if len(matches) == 1:
            entry = matches[0]

    if not entry:
        # Fall back to text search
        if teksto:
            entries = service.search_fts(demando, limit=limo)
        else:
            entries = service.search_like(demando, limit=limo)

        if not entries:
            info(tr("Neniuj rezultoj", "No results", "Aucun resultat"))
            return

        if len(entries) == 1:
            _copy_and_show(entries)
            return

        # Multiple results
        result = select_candidate(
            entries,
            columns=[
                {"header": "UUID", "style": "dim", "width": 10},
                {"header": "Titolo"},
            ],
            row_formatter=lambda e, i: [
                e.get("uuid", "")[:8],
                entry_locale_title(e, preferred_langs=preferred_search_langs),
            ],
        )
        if result is not None:
            idx, _ = result
            _copy_and_show(entries, idx)
        return

    # Graph-based search
    results: list[dict] = []
    seen_uuids: set = {entry.get("uuid")}

    if subklasoj:
        subclasses = service.get_subclasses(entry["uuid"])
        for sc in subclasses:
            if sc["entry"]["uuid"] not in seen_uuids:
                results.append(sc["entry"])
                seen_uuids.add(sc["entry"]["uuid"])

    if superklasoj:
        superclasses = service.get_superclasses(entry["uuid"])
        for sc in superclasses:
            if sc["entry"]["uuid"] not in seen_uuids:
                results.append(sc["entry"])
                seen_uuids.add(sc["entry"]["uuid"])

    # If no graph options, just show the entry
    if not (subklasoj or superklasoj):
        _copy_and_show([entry])
        return

    if not results:
        info(tr("Neniuj rezultoj", "No results", "Aucun resultat"))
        return

    if len(results) == 1:
        _copy_and_show(results)
        return

    result = select_candidate(
        results,
        columns=[
            {"header": "UUID", "style": "dim", "width": 10},
            {"header": "Titolo"},
        ],
        row_formatter=lambda e, i: [
            e.get("uuid", "")[:8],
            entry_locale_title(e, preferred_langs=preferred_search_langs),
        ],
    )
    if result is not None:
        idx, _ = result
        _copy_and_show(results, idx)


@app.command("grafo")
def grafo(
    ref: str = typer.Argument(
        ...,
        help=tr_multi("UUID au titolo", "UUID or title", "UUID ou titre"),
    ),
    profundeco: int = typer.Option(
        3,
        "-d",
        "--depth",
        help=tr_multi("Maksimuma profundeco", "Maximum depth", "Maximum depth"),
    ),
) -> None:
    """Show knowledge graph for an entry."""
    service = get_service()

    # Find entry
    entry = service.get(ref)
    if not entry:
        entry = service.find_by_titolo(ref)
    if not entry:
        matches = service.find_by_uuid_prefix(ref)
        if len(matches) == 1:
            entry = matches[0]

    if not entry:
        error(tr(f"Encik {ref} ne trovitas", f"Entry {ref} not found", f"Entree {ref} non trouve"))
        raise typer.Exit(1)

    graph = service.get_linked_graph(entry["uuid"], max_depth=profundeco)

    console.print(f"[bold]Grafo por:[/bold] {entry.get('titolo', entry['uuid'])}")
    console.print()

    if not graph["nodes"]:
        info(tr("Neniuj ligiloj", "No links", "Aucun lien"))
        return

    console.print("[bold]Nodoj:[/bold]")
    for node in graph["nodes"]:
        indent = "  " * node.get("depth", 0)
        console.print(f"{indent}[cyan]{node['uuid'][:8]}[/] {node.get('titolo', '')}")

    if graph["edges"]:
        console.print()
        console.print("[bold]Konektoj:[/bold]")
        for edge in graph["edges"]:
            console.print(f"  {edge['type']}: {edge.get('to', '')[:8]}")


@app.command("repacigi")
def repacigi() -> None:
    """Reconcile all bidirectional semantic links in the database."""
    service = get_service()
    count = service.reconcile_all_reverse_links()
    info(tr(f"Repacigis {count} ligilojn", f"Reconciled {count} links", f"Reconcile {count} liens"))


@app.command("eksporti")
def eksporti(
    ref: str = typer.Argument(
        ...,
        help=tr_multi("UUID aŭ titolo", "UUID or title", "UUID ou titre"),
    ),
    celvojo: str = typer.Argument(
        ...,
        help=tr_multi("Eliga dosiero", "Output file", "Output file"),
    ),
    formato: str = typer.Option(
        "enc",
        "--format",
        "-f",
        help=tr_multi("Formato: enc aŭ json", "Format: enc or json", "Format: enc or json"),
    ),
) -> None:
    """Export a knowledge entry."""
    import json

    service = get_service()

    # Find entry
    entry = service.get(ref)
    if not entry:
        entry = service.find_by_titolo(ref)
    if not entry:
        matches = service.find_by_uuid_prefix(ref)
        if matches:
            if len(matches) == 1:
                entry = matches[0]
            else:
                error(tr("Uz pli specifan referencon", "Use a more specific reference", "Uz pli specifan referencon"))
                raise typer.Exit(1)

    if not entry:
        error(tr(f"Encik {ref} ne trovitas", f"Entry {ref} not found", f"Entree {ref} non trouve"))
        raise typer.Exit(1)

    out_path = Path(celvojo).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if formato == "enc":
        from A_encik.enc_format import entry_to_enc
        enc_text = entry_to_enc(entry)
        out_path.write_text(enc_text, encoding="utf-8")
    else:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)

    info(tr(f"Eksportis {entry['titolo']} al {out_path}", f"Exported {entry['titolo']} to {out_path}", f"Exporte {entry['titolo']} vers {out_path}"))


@app.command("importi")
def importi(
    fonto: str = typer.Argument(
        ...,
        help=tr_multi("Eniga .enc dosiero", "Input .enc file", "Input .enc file"),
    ),
) -> None:
    """Import a knowledge entry from .enc file."""
    from A_encik.enc_format import parse_enc_file, validate_enc_entry

    path = Path(fonto).expanduser()
    if not path.exists():
        error(tr(f"Dosiero {fonto} ne ekzistas", f"File {fonto} does not exist", f"Fichier {fonto} n'existe pas"))
        raise typer.Exit(1)

    try:
        entry = parse_enc_file(path)
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(1)

    # Validate
    errors = validate_enc_entry(entry)
    if errors:
        for e in errors:
            error(f"Validiga eraro: {e}")
        raise typer.Exit(1)

    # Create entry
    service = get_service()
    created = service.create(entry)

    info(tr(f"Importis {created['titolo']}", f"Imported {created['titolo']}", f"Importé {created['titolo']}"))


@app.command("agordi")
def agordi() -> None:
    """Display current settings."""
    from A import load_config
    
    config = load_config()
    console.print("[bold]Encik Agordo[/bold]")
    console.print(f"  Language: {config.language}")


# ──────────────────────────────────────────────────────────────────────────────
# Rubujo (Recycle Bin) commands
# ──────────────────────────────────────────────────────────────────────────────

rubujo_app = typer.Typer(name="rubujo", help=tr_multi("Rubujo", "Recycle bin", "Recycle bin"))


@rubujo_app.command("ls")
def rubujo_ls(
    limo: int = typer.Option(50, "--limo", "-n", help=tr_multi("Maksimum da ensxtoj", "Max entries to show", "Max entries to show")),
) -> None:
    """List trashed entries."""
    service = get_service()
    entries = service.get_trash(limit=limo)

    if not entries:
        info(tr("Rubujo estas malplena", "Recycle bin is empty", "Rubujo estas malplena"))
        return

    console.print(f"[bold]{tr('Rubujo', 'Recycle bin', 'Rubujo')}[/bold]")
    console.print(f"  {tr('Nb entries:', 'Nb entries:', 'Nombro da ensxtoj:')} {len(entries)}")
    console.print()

    for entry in entries:
        title = entry.get("titolo", entry.get("uuid", ""))
        deleted_at = entry.get("forigita_je", "")
        console.print(f"  [dim]{deleted_at[:19]}[/dim]  {title}")


@rubujo_app.command("restaur")
def rubujo_restauri(
    ref: str = typer.Argument(..., help=tr_multi("UUID au titolo", "UUID or title", "UUID ou titre")),
) -> None:
    """Restore entry from recycle bin."""
    service = get_service()

    # Try to find in trash by UUID or title
    entry = None
    for trashed in service.get_trash(limit=1000):
        if trashed.get("uuid") == ref or trashed.get("titolo") == ref:
            entry = trashed
            break

    if not entry:
        error(tr(f"Eniro {ref} ne trovitas en rubujo", f"Entry {ref} not found in trash", f"Ensxto {ref} ne trovita en rubujo"))
        raise typer.Exit(1)

    service.restore(entry["uuid"])
    info(tr(f"Restaŭris {entry['titolo']}", f"Restored {entry['titolo']}", f"Restaŭris {entry['titolo']}"))


@rubujo_app.command("malplenigi")
def rubujo_malplenigi(
    konfirmi: bool = typer.Option(False, "--jes", "-y", help=tr_multi("Konfirmi sen demande", "Confirm without prompt", "Confirm without prompt")),
) -> None:
    """Empty the recycle bin."""
    if not konfirmi:
        console.print(tr("Uz --jes por konfirmi", "Use --jes to confirm", "Uzu --jes por konfirmi"))
        raise typer.Exit(1)

    service = get_service()
    count = service.empty_trash()
    info(tr(f"Malplenigis rubujon ({count} ensxtoj)", f"Emptied trash ({count} entries)", f"Malplenigis rubujon ({count} ensxtoj)"))


@rubujo_app.command("forigi")
def rubujo_permanent_forigi(
    ref: str = typer.Argument(..., help=tr_multi("UUID au titolo", "UUID or title", "UUID ou titre")),
    konfirmi: bool = typer.Option(False, "--jes", "-y", help=tr_multi("Konfirmi sen demande", "Confirm without prompt", "Confirm without prompt")),
) -> None:
    """Permanently delete entry from recycle bin."""
    if not konfirmi:
        console.print(tr("Uz --jes por konfirmi", "Use --jes to confirm", "Uzu --jes por konfirmi"))
        raise typer.Exit(1)

    service = get_service()

    # Find in trash
    entry = None
    for trashed in service.get_trash(limit=1000):
        if trashed.get("uuid") == ref or trashed.get("titolo") == ref:
            entry = trashed
            break

    if not entry:
        error(tr(f"Eniro {ref} ne trovitas en rubujo", f"Entry {ref} not found in trash", f"Ensxto {ref} ne trovita en rubujo"))
        raise typer.Exit(1)

    service.permanent_delete(entry["uuid"])
    info(tr(f"Forigis {entry['titolo']} permanenta", f"Permanently deleted {entry['titolo']}", f"Forigis {entry['titolo']} permanente"))


# Register rubujo as subcommand
app.add_typer(rubujo_app, name="rubujo")


# Phase 2 commands (TODO stubs)
@app.command("generi")
def generi() -> None:
    """Generate entry with AI (TODO)."""
    info("[dim]TODO: implement generi - requires A-AI rewrite[/dim]")


# ──────────────────────────────────────────────────────────────────────────────
# Semantika sub-typer
# ──────────────────────────────────────────────────────────────────────────────

from A_encik.semantika import (
    SEMANTIKA_HELPO_TEKSTO,
    ensure_semantika_group_files,
    load_semantika_groups,
    normalize_semantika_add_id,
    normalize_semantika_group_name,
    runtime_known_semantika_ligiloj,
    write_semantika_group_rows,
)
from A_encik.semantika.wikidata import (
    semantika_search_languages,
    wikidata_property_metadata,
    wikidata_search_properties,
)
from A_encik.semantika.search import parse_semantika_serci_conditions

# Lazy-loaded group command tracking
_REGISTERED_GROUP_COMMANDS: set[str] = set()


def _print_semantika_kategorio(kategorio: str) -> None:
    """Print semantic links in a category."""
    groups = load_semantika_groups()
    rows = groups.get(kategorio)
    if not rows:
        error(tr(f"Nekonata semantika grupo: {kategorio!r}", f"Unknown semantika group: {kategorio!r}", f"Groupe semantika inconnu : {kategorio!r}"))
        raise typer.Exit(1)
    info(tr(f"Semantikaj ligiloj — {kategorio}", f"Semantic links — {kategorio}", f"Liens semantiques — {kategorio}"))
    for row in rows:
        ligilo = str(row.get("ligilo") or "")
        priskribo = str(row.get("priskribo") or "")
        aliases = [str(a) for a in (row.get("aliasoj") or [])]
        alias_text = ", ".join(aliases[:5]) if aliases else "-"
        if len(aliases) > 5:
            alias_text += ", ..."
        console.print(f"  [cyan]{ligilo}[/]")
        console.print(f"    {priskribo} [dim]({alias_text})[/dim]")


def _register_semantika_group_commands() -> None:
    """Dynamically register one command per group CSV file."""
    groups = load_semantika_groups()
    for group_name in sorted(groups.keys()):
        if group_name in {"serci", "aldoni"} or group_name in _REGISTERED_GROUP_COMMANDS:
            continue
        help_text = f"Montri semantikajn ligilojn de grupo '{group_name}'."

        def _make_cmd(g: str = group_name) -> None:
            _print_semantika_kategorio(g)

        semantika_app.command(group_name, help=help_text)(_make_cmd)
        _REGISTERED_GROUP_COMMANDS.add(group_name)


semantika_app = typer.Typer(
    name="semantika",
    help=SEMANTIKA_HELPO_TEKSTO,
    no_args_is_help=False,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)


@semantika_app.callback(invoke_without_command=True)
def _semantika_root(ctx: typer.Context) -> None:
    _register_semantika_group_commands()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@semantika_app.command("serci")
def semantika_ligilo_serci(
    demando: str = typer.Argument(
        ...,
        help=tr_multi("Requête de recherche pour LIGILO/PRISKRIBO/ALIAZOJ", "Search query for LIGILO/PRISKRIBO/ALIAZOJ", "Search query for LIGILO/PRISKRIBO/ALIAZOJ"),
    ),
    lingvo: Optional[str] = typer.Option(
        None, "-l", "--lingvo",
        help=tr_multi("Code(s) de langue pour la recherche Wikidata (ex: eo,en)", "Language code(s) for Wikidata search (e.g. eo,en)", "Code(s) de langue pour la recherche Wikidata (ex: eo,en)"),
    ),
) -> None:
    """Search Wikidata for semantic link types."""
    needle = demando.strip().lower()
    if not needle:
        error(tr("Mankas serĉdemando.", "Missing search query.", "Requête de recherche manquante."))
        raise typer.Exit(1)
    try:
        languages = semantika_search_languages(lingvo)
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(1) from exc

    # Local CSV search
    local_matches: list[dict[str, object]] = []
    for group_name, rows in load_semantika_groups().items():
        for row in rows:
            ligilo = str(row.get("ligilo") or "")
            priskribo = str(row.get("priskribo") or "")
            aliases = [str(a) for a in (row.get("aliasoj") or [])]
            haystack = [ligilo, priskribo, *aliases]
            if any(needle in value.lower() for value in haystack if value):
                local_matches.append({
                    "fonto": "loka",
                    "grupo": group_name,
                    "ligilo": ligilo,
                    "priskribo": priskribo,
                    "aliasoj": aliases,
                })

    # Wikidata search
    wikidata_matches: list[dict[str, object]] = []
    wikidata_warning = ""
    try:
        wikidata_matches = wikidata_search_properties(demando, languages)
    except RuntimeError as exc:
        wikidata_warning = str(exc)

    if not local_matches and not wikidata_matches:
        info(tr("Neniuj rezultoj.", "No results.", "Aucun résultat."))
        if wikidata_warning:
            info(f"[dim]{wikidata_warning}[/dim]")
        return

    # Display local matches
    if local_matches:
        info(tr("Lokaj rezultoj:", "Local results:", "Résultats locaux :"))
        for m in local_matches:
            ligilo = str(m.get("ligilo") or "")
            priskribo = str(m.get("priskribo") or "")
            grupo = str(m.get("grupo") or "")
            aliases = ", ".join(str(a) for a in (m.get("aliasoj") or []))
            console.print(f"  [cyan]{ligilo}[/] — {priskribo}")
            if aliases:
                console.print(f"    [dim]aliazoj: {aliases} (grupo: {grupo})[/dim]")

    # Display Wikidata matches
    if wikidata_matches:
        info(tr("Wikidata rezultoj:", "Wikidata results:", "Résultats Wikidata :"))
        for m in wikidata_matches:
            ligilo = str(m.get("ligilo") or "")
            etikedo = str(m.get("etikedo") or "")
            priskribo = str(m.get("priskribo") or "")
            aliases = ", ".join(str(a) for a in (m.get("aliasoj") or []))
            console.print(f"  [cyan]{ligilo}[/] — {etikedo}")
            if priskribo:
                console.print(f"    {priskribo}")
            if aliases:
                console.print(f"    [dim]aliazoj: {aliases}[/dim]")

    if wikidata_warning:
        info(f"[dim]{wikidata_warning}[/dim]")


@semantika_app.command("aldoni")
def semantika_ligilo_aldoni(
    identigilo: str = typer.Argument(..., help=tr_multi("Lien ou ID Wikidata (ex: P1082 ou wdt:P1082)", "Link or Wikidata ID (e.g. P1082 or wdt:P1082)", "Lien ou ID Wikidata (ex: P1082 ou wdt:P1082)")),
    grupo: str = typer.Argument(..., help=tr_multi("Groupe cible (nom du fichier CSV)", "Target group (CSV file name)", "Groupe cible (nom du fichier CSV)")),
    priskribo: Optional[str] = typer.Option(None, "-p", "--priskribo", help=tr_multi("Description manuelle pour le repli hors ligne", "Manual description for offline fallback", "Manual description for offline fallback")),
    aliazoj: Optional[str] = typer.Option(None, "-a", "--aliazoj", help=tr_multi("Alias manuels (CSV) pour le repli hors ligne", "Manual aliases (CSV) for offline fallback", "Alias manuels (CSV) pour le repli hors ligne")),
    lingvo: Optional[str] = typer.Option(None, "-l", "--lingvo", help=tr_multi("Code(s) de langue pour les métadonnées Wikidata", "Language code(s) for Wikidata metadata", "Code(s) de langue pour les métadonnées Wikidata")),
) -> None:
    """Add a semantic link type to a group.
    
    Validates against Wikidata when possible; falls back to offline mode.
    """
    try:
        group_name = normalize_semantika_group_name(grupo)
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(1) from exc

    ligilo, prop_id = normalize_semantika_add_id(identigilo)
    groups = load_semantika_groups()

    if group_name not in groups:
        answer = typer.prompt(
            tr(f"Grupo '{group_name}' ne ekzistas. Ĉu krei ĝin? (j/N)", f"Group '{group_name}' doesn't exist. Create it? (j/N)", f"Le groupe '{group_name}' n'existe pas. Créer ? (j/N)"),
            default="n",
        )
        if answer.strip().lower() not in {"j", "jes", "y", "yes"}:
            info(tr("Nuligita.", "Cancelled.", "Annulé."))
            return
        groups[group_name] = []

    rows = [dict(row) for row in groups.get(group_name, [])]
    existing_index = next(
        (i for i, row in enumerate(rows) if str(row.get("ligilo") or "").strip().lower() == ligilo.lower()),
        None,
    )
    overwrite_existing = False
    if existing_index is not None:
        info(tr(f"Averto: {ligilo} jam ekzistas en grupo '{group_name}'.", f"Warning: {ligilo} already exists in group '{group_name}'.", f"Attention : {ligilo} existe déjà dans le groupe '{group_name}'."))
        answer = typer.prompt(
            tr("Ĉu anstataŭigi? (j/N)", "Replace? (j/N)", "Remplacer ? (j/N)"),
            default="n",
        )
        if answer.strip().lower() not in {"j", "jes", "y", "yes"}:
            info(tr("Nuligita.", "Cancelled.", "Annulé."))
            return
        overwrite_existing = True

    resolved_desc = priskribo or ""
    resolved_aliases = _parse_semantika_aliazoj(aliazoj or "")
    if prop_id and not resolved_desc:
        try:
            languages = semantika_search_languages(lingvo)
            meta = wikidata_property_metadata(prop_id, languages)
            if str(meta.get("priskribo") or "").strip():
                resolved_desc = str(meta.get("priskribo") or "").strip()
            meta_aliases = [str(v) for v in (meta.get("aliasoj") or []) if str(v)]
            for alias in meta_aliases:
                if alias.lower() not in {a.lower() for a in resolved_aliases}:
                    resolved_aliases.append(alias)
        except RuntimeError as exc:
            if not priskribo:
                error(tr(
                    f"Averto: {exc}. Uzu --priskribo por offline aldono.",
                    f"Warning: {exc}. Use --priskribo for offline add.",
                    f"Attention : {exc}. Utilisez --priskribo pour l'ajout hors ligne.",
                ))
                raise typer.Exit(1) from exc

    new_row = {"ligilo": ligilo, "priskribo": resolved_desc, "aliasoj": resolved_aliases}
    if overwrite_existing and existing_index is not None:
        rows[existing_index] = new_row
    else:
        rows.append(new_row)
    write_semantika_group_rows(group_name, rows)
    from A_encik.semantika.config import invalidate_config_cache
    invalidate_config_cache()
    _register_semantika_group_commands()

    info(tr(f"Aldonis {ligilo} al grupo '{group_name}'.", f"Added {ligilo} to group '{group_name}'.", f"Ajouté {ligilo} au groupe '{group_name}'."))


def _parse_semantika_aliazoj(raw: str) -> list[str]:
    """Parse comma-separated alias string."""
    return [token.strip() for token in str(raw or "").split(",") if token.strip()]


app.add_typer(semantika_app, name="semantika")
_register_semantika_group_commands()


@app.command("semantika-serci")
def semantika_serci(
    esprimo: str = typer.Argument(
        ...,
        help=tr_multi("wdt:P1082 (0,1000); wdt:P31 true", "Conditions separated by ';'. Examples:\n", "Conditions separated by ';'. Examples:\n"),
    ),
) -> None:
    """Search entries by semantic conditions (AND between conditions).

    Each condition: ARKO valoro, separated by ';'.

    Value types:
    - Range: (min,max) — numeric range
    - Boolean: true/false
    - Text: literal with * wildcard support
    """
    service = get_service()

    try:
        conditions = parse_semantika_serci_conditions(esprimo)
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(1) from exc

    matches = service.search_semantika(conditions)

    if not matches:
        info(tr("Neniu nodo trovita por semantika-serĉo.", "No entries found for semantic search.", "Aucune entrée trouvée pour la recherche sémantique."))
        return

    if len(matches) == 1:
        _display_semantika_match(matches[0])
        return

    info(tr(f"{len(matches)} nodo(j) trovitaj.", f"{len(matches)} entry(ies) found.", f"{len(matches)} entrée(s) trouvée(s)."))
    for entry in matches:
        uuid = str(entry.get("uuid", ""))[:8]
        titolo = entry.get("titolo", "")
        console.print(f"  [cyan]{uuid}[/] {titolo}")


def _display_semantika_match(entry: dict) -> None:
    """Display a single semantic search match inline."""
    uuid = entry.get("uuid", "")
    titolo = entry.get("titolo", "")
    console.print(f"[bold cyan]UUID:[/] {uuid}")
    console.print(f"[bold cyan]Titolo:[/] {titolo}")
    semantikaj = entry.get("semantika", [])
    if semantikaj:
        console.print("[bold cyan]Semantiko:[/]")
        for item in (semantikaj if isinstance(semantikaj, list) else []):
            if isinstance(item, dict):
                tipo = item.get("tipo", "")
                arko = item.get("arko", "")
                valoro = item.get("valoro", "")
                unuo = item.get("unuo", "")
                line = f"  {tipo} {arko} = {valoro}"
                if unuo:
                    line += f" [{unuo}]"
                console.print(line)


__all__ = ["app"]