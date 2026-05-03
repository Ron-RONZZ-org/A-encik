"""CLI for encik command."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from A import error, info
from A.console import console, tr

from A_encik.service import get_service

app = typer.Typer(
    name="encik",
    help=tr(
        "Encik — persona sci-mastruma mikroapo.",
        "Encik — personal knowledge management microapp.",
        "Encik — microapplication de gestion de connaissances.",
    ),
    no_args_is_help=False,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)


@app.command("ls")
def ls(
    order_by: str = typer.Option(
        "kreita_je",
        "--order-by",
        "-o",
        help=tr("Order by field", "Order by field", "Champ de tri"),
    ),
    desc: bool = typer.Option(
        True,
        "--desc",
        "-d",
        help=tr("Descending order", "Descending order", "Ordre decroissant"),
    ),
    limit: Optional[int] = typer.Option(
        10,
        "--limit",
        "-l",
        help=tr("Limit results", "Limit results", "Limiter les resultats"),
    ),
    pagina: Optional[int] = typer.Option(
        None,
        "--pagho",
        "-p",
        help=tr("Page number (1-indexed)", "Page number (1-indexed)", "Numero de paĝo"),
    ),
) -> None:
    """List knowledge entries."""
    service = get_service()
    entries = service.list(order_by=order_by, desc=desc, limit=limit)
    
    if not entries:
        info(tr("Neniuj videblas", "No entries found", "Aucune entree"))
        return
    
    for entry in entries:
        uuid = entry.get("uuid", "")[:8]
        titolo = entry.get("titolo", "")
        console.print(f"[cyan]{uuid}[/] [bold]{titolo}[/]")


@app.command("vidi")
def vidi(
    ref: str = typer.Argument(
        ...,
        help=tr("UUID or title", "UUID or title", "UUID aŭ titolo"),
    ),
    lingvo: Optional[str] = typer.Option(
        None,
        "-l",
        "--lingvo",
        help=tr("Language code", "Language code", "Kodo de lingvo"),
    ),
    html: bool = typer.Option(
        False,
        "--html",
        "-H",
        help=tr("Render as HTML", "Render as HTML", "Montri kiel HTML"),
    ),
    open_browser: bool = typer.Option(
        False,
        "--open",
        "-o",
        help=tr("Open in browser", "Open in browser", "Malfermi en retumilo"),
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

    # HTML rendering
    if html or open_browser:
        from A_encik.display import preview_entry
        preview_entry(entry, open_browser=open_browser)
        if open_browser:
            info(tr("Malfermis en retumilo", "Opened in browser", "Ouvert dans le navigateur"))
        return

    if not entry:
        error(tr(f"Encik {ref} ne trovitas", f"Entry {ref} not found", f"Entree {ref} non trouve"))
        raise typer.Exit(1)
    
    # Display entry
    console.print(f"[bold cyan]UUID:[/] {entry.get('uuid')}")
    console.print(f"[bold cyan]Titolo:[/] {entry.get('titolo')}")
    
    if entry.get("difinio"):
        console.print(f"[bold cyan]Difino:[/] {entry.get('difinio')}")
    
    terminologio = entry.get("terminologio", {})
    if terminologio:
        console.print("[bold cyan]Terminologio:[/]")
        for lang, term in terminologio.items():
            console.print(f"  {lang}: {term}")
    
    difinoj = entry.get("difinoj", {})
    if difinoj:
        console.print("[bold cyan]Difinoj:[/]")
        for lang, defin in difinoj.items():
            console.print(f"  {lang}: {defin}")
    
    if entry.get("enhavo"):
        console.print(f"[bold cyan]Enhavo:[/] {entry.get('enhavo')}")
    
    superklaso = entry.get("superklaso", [])
    if superklaso:
        console.print("[bold cyan]Superklaso:[/]")
        for sk in superklaso:
            console.print(f"  - {sk}")
    
    ligilo = entry.get("ligilo", [])
    if ligilo:
        console.print("[bold cyan]Ligilo:[/]")
        for link in ligilo:
            console.print(f"  - {link}")
    
    fonto = entry.get("fonto", [])
    if fonto:
        console.print("[bold cyan]Fonto:[/]")
        for f in fonto:
            console.print(f"  - {f}")
    
    console.print(f"[bold cyan]Kreita:[/] {entry.get('kreita_je')}")
    console.print(f"[bold cyan]Modifita:[/] {entry.get('modifita_je')}")


@app.command("aldoni")
def aldoni(
    titolo: str = typer.Argument(..., help=tr("Title", "Title", "Titolo")),
    difinio: Optional[str] = typer.Option(None, "-d", "--difino", help=tr("Definition", "Definition", "Difino")),
    enhavo: Optional[str] = typer.Option(None, "-e", "--enhavo", help=tr("Content", "Content", "Enhavo")),
    terminologio: Optional[str] = typer.Option(None, "-t", "--terminologio", help=tr("Terminology (JSON)", "Terminology (JSON)", "Terminologio (JSON)")),
    superklaso: Optional[str] = typer.Option(None, "-s", "--superklaso", help=tr("Superclass UUIDs (JSON)", "Superclass UUIDs (JSON)", "Superklaso UUIDoj (JSON)")),
    ligilo: Optional[str] = typer.Option(None, "-l", "--ligilo", help=tr("Links (JSON)", "Links (JSON)", "Ligiloj (JSON)")),
    fonto: Optional[str] = typer.Option(None, "-f", "--fonto", help=tr("Sources (JSON)", "Sources (JSON)", "Fontoj (JSON)")),
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


@app.command("modifi")
def modifi(
    ref: str = typer.Argument(
        ...,
        help=tr("UUID or title", "UUID or title", "UUID aŭ titolo"),
    ),
    titolo: Optional[str] = typer.Option(None, "-t", "--titolo", help=tr("New title", "New title", "Nova titolo")),
    difinio: Optional[str] = typer.Option(None, "-d", "--difino", help=tr("New definition", "New definition", "Nova difino")),
    enhavo: Optional[str] = typer.Option(None, "-e", "--enhavo", help=tr("New content", "New content", "Nova enhavo")),
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


@app.command("forigi")
def forigi(
    ref: str = typer.Argument(
        ...,
        help=tr("UUID or title", "UUID or title", "UUID aŭ titolo"),
    ),
    hard: bool = typer.Option(
        False,
        "--hard",
        "-H",
        help=tr("Permanent delete (no trash)", "Permanent delete (no trash)", "Suppression permanente"),
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
    demando: str = typer.Argument(
        ...,
        help=tr("Search query", "Search query", "Serĉa demando"),
    ),
    teksto: bool = typer.Option(
        False,
        "-t",
        "--teksto",
        help=tr("Search full text (not just title)", "Search full text (not just title)", "Ser��i plenan tekston"),
    ),
    limit: int = typer.Option(
        20,
        "-l",
        "--limit",
        help=tr("Maximum results", "Maximum results", "Maksimumaj rezultoj"),
    ),
) -> None:
    """Search knowledge entries."""
    service = get_service()
    
    if teksto:
        entries = service.search_fts(demando, limit=limit)
    else:
        entries = service.search_like(demando, limit=limit)
    
    if not entries:
        info(tr("Neniuj rezultoj", "No results", "Aucun resultat"))
        return
    
    for entry in entries:
        uuid = entry.get("uuid", "")[:8]
        titolo = entry.get("titolo", "")
        console.print(f"[cyan]{uuid}[/] [bold]{titolo}[/]")
    
    info(tr(f"{len(entries)} rezultoj", f"{len(entries)} results", f"{len(entries)} resultats"))


@app.command("eksporti")
def eksporti(
    ref: str = typer.Argument(
        ...,
        help=tr("UUID or title", "UUID or title", "UUID aŭ titolo"),
    ),
    celvojo: str = typer.Argument(
        ...,
        help=tr("Output file", "Output file", "Eliga dosiero"),
    ),
    formato: str = typer.Option(
        "enc",
        "--format",
        "-f",
        help=tr("Format: enc or json", "Format: enc or json", "Formato: enc aŭ json"),
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
        help=tr("Input .enc file", "Input .enc file", "Eniga .enc dosiero"),
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

rubujo_app = typer.Typer(name="rubujo", help=tr("Recycle bin", "Recycle bin", "Rubujo"))


@rubujo_app.command("list")
def rubujo_list(
    limo: int = typer.Option(50, "--limo", "-n", help=tr("Max entries to show", "Max entries to show", "Maksimum da ensxtoj")),
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
    ref: str = typer.Argument(..., help=tr("UUID or title", "UUID or title", "UUID au titolo")),
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
    konfirmi: bool = typer.Option(False, "--jes", "-y", help=tr("Confirm without prompt", "Confirm without prompt", "Konfirmi sen demande")),
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
    ref: str = typer.Argument(..., help=tr("UUID or title", "UUID or title", "UUID au titolo")),
    konfirmi: bool = typer.Option(False, "--jes", "-y", help=tr("Confirm without prompt", "Confirm without prompt", "Konfirmi sen demande")),
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
        help=tr("Search query for LIGILO/PRISKRIBO/ALIAZOJ", "Search query for LIGILO/PRISKRIBO/ALIAZOJ", "Requête de recherche pour LIGILO/PRISKRIBO/ALIAZOJ"),
    ),
    lingvo: Optional[str] = typer.Option(
        None, "-l", "--lingvo",
        help=tr("Language code(s) for Wikidata search (e.g. eo,en)", "Language code(s) for Wikidata search (e.g. eo,en)", "Code(s) de langue pour la recherche Wikidata (ex: eo,en)"),
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
    identigilo: str = typer.Argument(..., help=tr("Link or Wikidata ID (e.g. P1082 or wdt:P1082)", "Link or Wikidata ID (e.g. P1082 or wdt:P1082)", "Lien ou ID Wikidata (ex: P1082 ou wdt:P1082)")),
    grupo: str = typer.Argument(..., help=tr("Target group (CSV file name)", "Target group (CSV file name)", "Groupe cible (nom du fichier CSV)")),
    priskribo: Optional[str] = typer.Option(None, "-p", "--priskribo", help=tr("Manual description for offline fallback", "Manual description for offline fallback", "Description manuelle pour le repli hors ligne")),
    aliazoj: Optional[str] = typer.Option(None, "-a", "--aliazoj", help=tr("Manual aliases (CSV) for offline fallback", "Manual aliases (CSV) for offline fallback", "Alias manuels (CSV) pour le repli hors ligne")),
    lingvo: Optional[str] = typer.Option(None, "-l", "--lingvo", help=tr("Language code(s) for Wikidata metadata", "Language code(s) for Wikidata metadata", "Code(s) de langue pour les métadonnées Wikidata")),
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
        help=tr(
            "Conditions separated by ';'. Examples:\n"
            '  encik semantika-serci "wdt:P5191 *philosophia*"\n'
            '  encik semantika-serci "wdt:P1082 (0,1000); wdt:P31 true"',
            "Conditions separated by ';'. Examples:\n"
            '  encik semantika-serci "wdt:P5191 *philosophia*"\n'
            '  encik semantika-serci "wdt:P1082 (0,1000); wdt:P31 true"',
            "Conditions séparées par ';'. Exemples :\n"
            '  encik semantika-serci "wdt:P5191 *philosophia*"\n'
            '  encik semantika-serci "wdt:P1082 (0,1000); wdt:P31 true"',
        ),
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