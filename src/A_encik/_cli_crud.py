"""CRUD commands: ls, vidi, aldoni, modifi, forigi."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table
from rich.box import SIMPLE as BOX_SIMPLE

from A import error, info, warning, copy_to_clipboard
from A.console import console
from A import tr_multi
from rich.panel import Panel

from A_encik.service import get_service
from A_encik.display_helpers import (
    preferred_lang,
    entry_locale_title,
    entry_display_name,
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

        table = Table(show_header=True, expand=False, box=BOX_SIMPLE)
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
            help=tr_multi(
                "UUID, titolo, aŭ .enc dosiero por antaŭrigardo",
                "UUID, title, or .enc file for preview",
                "UUID, titre, ou fichier .enc pour prévisualisation",
            ),
        ),
        lingvo: Optional[str] = typer.Option(
            None,
            "-l",
            "--lingvo",
            help=tr_multi("Kodo de lingvo", "Language code", "Code de langue"),
        ),
        cio: bool = typer.Option(
            False,
            "-a",
            "--cio",
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
            help=tr_multi("Kopii [terminologio.uzantLingvo](#uuid) al tondujo", "Copy [title in user language](#uuid) to clipboard", "Copier [titre dans la langue de l'utilisateur](#uuid) dans le presse-papier"),
        ),
    ) -> None:
        """View a knowledge entry (or preview a .enc file before addition)."""
        service = get_service()

        # File preview mode: if ref is a .enc file, parse and display without DB
        ref_path = Path(ref).expanduser().resolve()
        if ref_path.suffix == ".enc" and ref_path.exists():
            from A_encik.enc_format import parse_enc_file, validate_enc_entry

            try:
                parsed = parse_enc_file(ref_path)
            except ValueError as exc:
                error(str(exc))
                raise typer.Exit(1)
            errors = validate_enc_entry(parsed)
            if errors:
                for e in errors:
                    error(f"Validiga eraro: {e}")
                raise typer.Exit(1)

            if kopii or semantika_kopii:
                warning(tr_multi(
                    "Antaŭrigardo ne havas UUID-on — tondujo ne uzeblas",
                    "Preview has no UUID — clipboard not available",
                    "L'aperçu n'a pas d'UUID — presse-papier non disponible",
                ))
                kopii = False
                semantika_kopii = False

            if html or open_browser:
                from A_encik.display import preview_entry
                path = preview_entry(parsed)
                info(tr_multi(
                    f"Aldono HTML: file://{path}",
                    f"HTML preview: file://{path}",
                    f"Aperçu HTML: file://{path}",
                ))
                return

            from A_encik.display_helpers import entry_locale_title as _elt
            title = _elt(parsed) or ref_path.stem
            lines: list[str] = []
            lines.append(f"  [dim]{'stato:':<14}[/dim] [italic]antaŭrigardo[/italic]")
            lines.append(f"  [dim]{'fonto:':<14}[/dim] {ref_path}")
            # Show terminologio as inline summary
            term = parsed.get("terminologio") or {}
            if term:
                term_str = " | ".join(f"{k}: {v}" for k, v in term.items() if v)
                lines.append(f"  [dim]{'terminologio:':<14}[/dim] {term_str}")
            dif = parsed.get("difinoj") or parsed.get("difinio") or ""
            if dif:
                if isinstance(dif, dict):
                    dif = next(iter(dif.values()), "")
                first_line = str(dif).strip().split("\n")[0][:80]
                lines.append(f"  [dim]{'difino:':<14}[/dim] {first_line}")
            console.print(Panel("\n".join(lines), title=f"[bold]{title}[/bold]", expand=False))
            return

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
            path = preview_entry(entry)
            info(tr_multi(
                f"Aldono HTML: file://{path}",
                f"HTML preview: file://{path}",
                f"Aperçu HTML: file://{path}",
            ))
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
        display_entry_panel(entry, selected_lang=selected_lang, cxio=cio)

    @app.command("modifi")
    def modifi(
        ref: str = typer.Argument(
            ...,
            help=tr_multi("UUID aŭ titolo", "UUID or title", "UUID ou titre"),
        ),
        dosiero: Optional[Path] = typer.Argument(
            None,
            help=tr_multi(
                ".enc dosiero por rekta anstataŭigo. "
                "Ligilo ekz: ligilo = [[\"uuid\", \"tipo\"]]",
                ".enc file for full replacement. "
                "ligilo format: ligilo = [[\"uuid\", \"tipo\"]]",
                "Fichier .enc pour remplacement complet. "
                "Format ligilo : ligilo = [[\"uuid\", \"tipo\"]]",
            ),
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
            help=tr_multi("Kopii [terminologio.uzantLingvo](#uuid) al tondujo", "Copy [title in user language](#uuid) to clipboard", "Copier [titre dans la langue de l'utilisateur](#uuid) dans le presse-papier"),
        ),
        vidi: bool = typer.Option(
            False,
            "-v",
            "--vidi",
            help=tr_multi(
                "Montri la modifitan nodon post konservado",
                "Show the modified entry after saving",
                "Afficher l'entrée modifiée après sauvegarde",
            ),
        ),
        html: bool = typer.Option(
            False,
            "-H",
            "--html",
            help=tr_multi(
                "Kun --vidi: montri kiel HTML en retumilo",
                "With --vidi: show as HTML in browser",
                "Avec --vidi: afficher en HTML dans le navigateur",
            ),
        ),
    ) -> None:
        """Modify a knowledge entry."""
        if kopii and semantika_kopii:
            error(tr_multi(
                "Uzu nur unu el --kopii aŭ --semantika-kopii.",
                "Use only one of --kopii or --semantika-kopii.",
                "Utilisez un seul de --kopii ou --semantika-kopii.",
            ))
            raise typer.Exit(1)

        if html and not vidi:
            vidi = True

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

        if dosiero is None:
            error(tr_multi(
                "Mankas .enc dosiero. Uzu: encik modifi <uuid> <dosiero.enc>",
                "Missing .enc file. Usage: encik modifi <uuid> <file.enc>",
                "Fichier .enc manquant. Usage: encik modifi <uuid> <fichier.enc>",
            ))
            raise typer.Exit(1)

        enc_path = dosiero.expanduser().resolve()
        if not enc_path.exists():
            error(tr_multi(
                f"Dosiero ne trovita: {enc_path}",
                f"File not found: {enc_path}",
                f"Fichier non trouvé: {enc_path}",
            ))
            raise typer.Exit(1)
        if not enc_path.is_file():
            error(tr_multi(
                f"Ne estas dosiero: {enc_path}",
                f"Not a file: {enc_path}",
                f"Ce n'est pas un fichier: {enc_path}",
            ))
            raise typer.Exit(1)

        from A_encik.enc_format import parse_enc_file, validate_enc_entry
        try:
            parsed = parse_enc_file(enc_path)
        except ValueError as exc:
            error(str(exc))
            raise typer.Exit(1)
        errors = validate_enc_entry(parsed)
        if errors:
            for e in errors:
                error(f"Validiga eraro: {e}")
            raise typer.Exit(1)

        updated = service.update(entry["uuid"], parsed)
        mod_name = entry_display_name(entry)
        info(tr_multi(
            f"Anstataŭigis {mod_name}",
            f"Replaced {mod_name}",
            f"Remplacé {mod_name}",
        ))
        console.print(f"[green]UUID:[/] {updated.get('uuid')}")

        if kopii or semantika_kopii:
            if kopii:
                copy_to_clipboard(f"#{updated['uuid'][:8]}")
            if semantika_kopii:
                copy_entry_reference(updated, semantika=True)

        if vidi:
            if html:
                from A_encik.display import preview_entry
                path = preview_entry(updated)
                info(tr_multi(
                    f"Aldono HTML: file://{path}",
                    f"HTML preview: file://{path}",
                    f"Aperçu HTML: file://{path}",
                ))
            else:
                display_entry_panel(updated)

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
            help=tr_multi("Forigi permanente (preterrubujo)", "Permanent delete (no trash)", "Suppression définitive (pas de corbeille)"),
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
                    n = entry_display_name(entry)
                    info(tr_multi(f"Forigis {n} (sxoveblas)", f"Deleted {n} (soft)", f"Supprime {n} ( mou)"))
                else:
                    n = entry_display_name(entry)
                    info(tr_multi(f"Forigis {n} (permanenta)", f"Deleted {n} (permanent)", f"Supprime {n} (permanent)"))
            except Exception as e:
                error(str(e))
