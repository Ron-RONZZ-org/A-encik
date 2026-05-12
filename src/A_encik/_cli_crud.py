"""CRUD commands: ls, vidi, aldoni, modifi, forigi."""

from __future__ import annotations

from typing import Annotated, Optional

import typer
from rich.table import Table

from A import error, info, copy_to_clipboard
from A.console import console
from A import tr_multi

from A_encik.service import get_service
from A_encik.display_helpers import (
    preferred_lang,
    entry_locale_title,
    render_markdown_text,
    display_ligilo_items,
    copy_entry_reference,
)
from A_encik.display import display_entry_panel


def register_commands(app: typer.Typer) -> None:
    """Register CRUD commands on the given Typer app."""

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
        """List encik entries with pagination."""
        service = get_service()
        total = service.count()

        if total == 0:
            info(tr_multi("Neniu eniro en la datumbazo.", "No entries in the database.", "Aucune entrée dans la base."))
            return

        offset = (pagho - 1) * per_pagho
        total_pages = (total + per_pagho - 1) // per_pagho

        if offset >= total:
            error(tr_multi(
                f"Paĝo {pagho} ne ekzistas (nur {total_pages} paĝo(j)).",
                f"Page {pagho} does not exist (only {total_pages} page(s)).",
            ))
            raise typer.Exit(1)

        entries = service.list(order_by="kreita_je", desc=not inversa, limit=per_pagho, offset=offset)

        start = offset + 1
        end = min(offset + per_pagho, total)
        console.print(f"[dim]{tr_multi('Montras', 'Showing')} {start}-{end} {tr_multi('el', 'of')} {total} {tr_multi('eniro(j)', 'entry(ies)')} | {tr_multi('Paĝo', 'Page')} {pagho}/{total_pages}[/dim]")

        table = Table(show_header=True, expand=False)
        table.add_column("UUID", width=10, no_wrap=True)
        table.add_column(tr_multi("Titolo", "Title"), min_width=30)
        table.add_column(tr_multi("Kreita", "Created"), width=12)
        table.add_column(tr_multi("Modifita", "Modified"), width=12)

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

        entry = service.get(ref)
        if not entry:
            entry = service.find_by_titolo(ref)
        if not entry:
            matches = service.find_by_uuid_prefix(ref)
            if len(matches) == 1:
                entry = matches[0]

        if not entry:
            error(tr_multi(f"Encik {ref} ne trovitas", f"Entry {ref} not found", f"Entree {ref} non trouve"))
            raise typer.Exit(1)

        if html or open_browser:
            from A_encik.display import preview_entry
            preview_entry(entry, open_browser=True)
            info(tr_multi("Malfermis en retumilo", "Opened in browser", "Ouvert dans le navigateur"))
            return

        # Auto-open for KaTeX/images content
        from A_encik.display import maybe_auto_open_browser
        if maybe_auto_open_browser(entry):
            return

        if kopii or semantika_kopii:
            copy_entry_reference(entry, semantika=semantika_kopii)

        selected_lang = (lingvo or "").strip().lower() or preferred_lang(
            entry.get("terminologio") or {}, entry.get("difinoj") or {}
        )
        display_entry_panel(entry, selected_lang=selected_lang, cxio=cxio)

    @app.command(
        "aldoni",
        epilog=tr_multi(
            "\n.enc formato (por --terminologio, --difino ktp):\n"
            "  terminologio.eo = \"Termino\"\n"
            "  terminologio.en = \"Term\"\n"
            "  difino.eo = \"Difino\"\n"
            "  difino.en = \"Definition\"\n"
            "  enhavo = \"\"\"Plena enhavo...\"\"\"\n"
            "  superklaso = [\"uuid1\", \"uuid2\"]\n"
            "  ligilo = [\"uuid1\", [\"uuid2\", \"rdf:type\"]]\n"
            "  fonto = [{titolo=\"...\", autoro=\"...\", jaro=2024, tipo=\"lib\"}]\n"
            "  citajo = [{teksto=\"...\", autoro=\"...\", verko=\"...\"}]\n"
            "  datumo.nomo = \"\"\"{...json...}\"\"\"\n"
            "Vidu A-encik dokumentaron por plena .enc referenco.",
            "\n.enc format (for --terminologio, --difino etc.):\n"
            "  terminologio.eo = \"Term\"\n"
            "  terminologio.en = \"Term\"\n"
            "  difino.eo = \"Definition\"\n"
            "  difino.en = \"Definition\"\n"
            "  enhavo = \"\"\"Full content...\"\"\"\n"
            "  superklaso = [\"uuid1\", \"uuid2\"]\n"
            "  ligilo = [\"uuid1\", [\"uuid2\", \"rdf:type\"]]\n"
            "  fonto = [{title=\"...\", author=\"...\", year=2024, type=\"book\"}]\n"
            "  citajo = [{text=\"...\", author=\"...\", work=\"...\"}]\n"
            "  datumo.name = \"\"\"{...json...}\"\"\"\n"
            "See A-encik docs for full .enc reference.",
            "\nFormat .enc (pour --terminologio, --difino etc.) :\n"
            "  terminologio.eo = \"Terme\"\n"
            "  terminologio.en = \"Term\"\n"
            "  difino.eo = \"Definition\"\n"
            "  difino.en = \"Definition\"\n"
            "  enhavo = \"\"\"Contenu complet...\"\"\"\n"
            "  superklaso = [\"uuid1\", \"uuid2\"]\n"
            "  ligilo = [\"uuid1\", [\"uuid2\", \"rdf:type\"]]\n"
            "  fonto = [{title=\"...\", author=\"...\", year=2024, type=\"book\"}]\n"
            "  citajo = [{text=\"...\", author=\"...\", work=\"...\"}]\n"
            "  datumo.nom = \"\"\"{...json...}\"\"\"\n"
            "Voir documentation A-encik pour référence .enc complète.",
        ),
    )
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

        # Check for duplicate title (warn + prompt to replace, matching legacy)
        existing = service.find_by_titolo(titolo)
        if existing:
            error(tr_multi(
                f"Eniro '{titolo}' jam ekzistas (#{existing['uuid'][:8]}).",
                f"Entry '{titolo}' already exists (#{existing['uuid'][:8]}).",
                f"Entrée '{titolo}' existe déjà (#{existing['uuid'][:8]}).",
            ))
            answer = typer.prompt(
                tr_multi("Ĉu anstataŭigi? (j/N)", "Replace? (j/N)", "Remplacer ? (j/N)"),
                default="n",
            )
            if answer.strip().lower() not in {"j", "jes", "y", "yes"}:
                info(tr_multi("Nuligita.", "Cancelled.", "Annulé."))
                return
            # Update existing entry with provided fields (partial update)
            updated = service.update(existing["uuid"], data)
            info(tr_multi(f"Anstataŭigis {titolo}", f"Replaced {titolo}", f"Remplacé {titolo}"))
            console.print(f"[green]UUID:[/] {updated.get('uuid')}")
            if kopii or semantika_kopii:
                if kopii:
                    copy_to_clipboard(f"#{updated['uuid'][:8]}")
                if semantika_kopii:
                    copy_to_clipboard(f"[{updated['titolo']}](#{updated['uuid'][:8]})")
            return
        if difinio:
            data["difinio"] = difinio
        if enhavo:
            data["enhavo"] = enhavo

        if terminologio:
            try:
                data["terminologio"] = json.loads(terminologio)
            except json.JSONDecodeError:
                error(tr_multi("Nevalida JSON por terminologio", "Invalid JSON for terminologio", "JSON nevalida por terminologio"))
                raise typer.Exit(1)
        else:
            data["terminologio"] = {"eo": titolo}

        if superklaso:
            try:
                data["superklaso"] = json.loads(superklaso)
            except json.JSONDecodeError:
                error(tr_multi("Nevalida JSON por superklaso", "Invalid JSON for superklaso", "JSON nevalida por superklaso"))
                raise typer.Exit(1)

        if ligilo:
            try:
                data["ligilo"] = json.loads(ligilo)
            except json.JSONDecodeError:
                error(tr_multi("Nevalida JSON por ligilo", "Invalid JSON for ligilo", "JSON nevalida por ligilo"))
                raise typer.Exit(1)

        if fonto:
            try:
                data["fonto"] = json.loads(fonto)
            except json.JSONDecodeError:
                error(tr_multi("Nevalida JSON por fonto", "Invalid JSON for fonto", "JSON nevalida por fonto"))
                raise typer.Exit(1)

        entry = service.create(data)
        info(tr_multi(f"Aldonis {titolo}", f"Added {titolo}", f"Ajoute {titolo}"))
        console.print(f"[green]UUID:[/] {entry.get('uuid')}")

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

        entry = service.get(ref)
        if not entry:
            entry = service.find_by_titolo(ref)
        if not entry:
            matches = service.find_by_uuid_prefix(ref)
            if matches:
                if len(matches) == 1:
                    entry = matches[0]
                else:
                    error(tr_multi("Uz pli specifan referencon", "Use a more specific reference", "Uzu pli specifan referencon"))
                    raise typer.Exit(1)

        if not entry:
            error(tr_multi(f"Encik {ref} ne trovitas", f"Entry {ref} not found", f"Entree {ref} non trouve"))
            raise typer.Exit(1)

        data = {}
        if titolo:
            data["titolo"] = titolo
        if difinio is not None:
            data["difinio"] = difinio
        if enhavo is not None:
            data["enhavo"] = enhavo

        if not data:
            info(tr_multi("Neniuj sxangoj", "No changes", "Aucun changement"))
            return

        updated = service.update(entry["uuid"], data)
        info(tr_multi(f"Modifikis {updated['titolo']}", f"Modified {updated['titolo']}", f"Modifie {updated['titolo']}"))

        if kopii or semantika_kopii:
            if kopii:
                copy_to_clipboard(f"#{updated['uuid'][:8]}")
            if semantika_kopii:
                copy_to_clipboard(f"[{updated['titolo']}](#{updated['uuid'][:8]})")

    @app.command("forigi")
    def forigi(
        refs: Annotated[list[str], typer.Argument(
            ...,
            help=tr_multi("UUID aŭ titolo (pluraj)", "UUID or title (multiple)", "UUID ou titre (plusieurs)"),
        )],
        hard: bool = typer.Option(
            False,
            "--hard",
            "-H",
            help=tr_multi("Suppression permanente", "Permanent delete (no trash)", "Suppression définitive (pas de corbeille)"),
        ),
    ) -> None:
        """Delete knowledge entries."""
        service = get_service()
        for ref in refs:
            try:
                entry = service.get(ref)
                if not entry:
                    entry = service.find_by_titolo(ref)
                if not entry:
                    matches = service.find_by_uuid_prefix(ref)
                    if matches:
                        if len(matches) == 1:
                            entry = matches[0]
                        else:
                            error(tr_multi("Uz pli specifan referencon", "Use a more specific reference", "Uzu pli specifan referencon"))
                            continue

                if not entry:
                    error(tr_multi(f"Encik {ref} ne trovitas", f"Entry {ref} not found", f"Entree {ref} non trouve"))
                    continue

                uuid = entry["uuid"]
                soft = not hard
                service.delete(uuid, soft=soft)
                if soft:
                    info(tr_multi(f"Forigis {entry['titolo']} (sxoveblas)", f"Deleted {entry['titolo']} (soft)", f"Supprime {entry['titolo']} ( mou)"))
                else:
                    info(tr_multi(f"Forigis {entry['titolo']} (permanenta)", f"Deleted {entry['titolo']} (permanent)", f"Supprime {entry['titolo']} (permanent)"))
            except Exception as e:
                error(str(e))
