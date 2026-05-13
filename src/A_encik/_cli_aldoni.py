"""Aldoni command — add entry from .enc file or create time-based entries."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from A import error, info, copy_to_clipboard
from A.console import console
from A import tr_multi

from A_encik.service import get_service
from A_encik.display_helpers import copy_entry_reference
from A_encik.display import display_entry_panel


def _validate_time_args(
    jaro: int | None,
    jardeko: int | None,
    jarcento: int | None,
) -> bool:
    """Check mutual exclusion of time flags. Returns True if any set."""
    time_flags = [jaro, jardeko, jarcento]
    active = [f for f in time_flags if f is not None]
    if len(active) > 1:
        error(tr_multi(
            "Uzu nur unu el --jaro, --jardeko, --jarcento.",
            "Use only one of --jaro, --jardeko, --jarcento.",
            "Utilisez un seul de --jaro, --jardeko, --jarcento.",
        ))
        raise typer.Exit(1)
    return len(active) > 0


def register_commands(app: typer.Typer) -> None:
    """Register the aldoni command on the given Typer app."""

    @app.command("aldoni")
    def aldoni(
        dosiero: Optional[str] = typer.Argument(
            None,
            help=tr_multi(
                "Vojo al .enc dosiero (malnepra se --jaro/-jardeko/-jarcento uzatas)",
                "Path to .enc file (optional if --jaro/--jardeko/--jarcento used)",
                "Chemin vers fichier .enc (optionnel si --jaro/--jardeko/--jarcento utilisé)",
            ),
        ),
        jaro: Optional[int] = typer.Option(
            None,
            "--jaro",
            "-j",
            help=tr_multi(
                "Krei jar-eniron (1-3000)",
                "Create year entry (1-3000)",
                "Créer une entrée d'année (1-3000)",
            ),
        ),
        jardeko: Optional[int] = typer.Option(
            None,
            "--jardeko",
            "-jd",
            help=tr_multi(
                "Krei jardek-eniron (oblo de 10)",
                "Create decade entry (multiple of 10)",
                "Créer une entrée de décennie (multiple de 10)",
            ),
        ),
        jarcento: Optional[int] = typer.Option(
            None,
            "--jarcento",
            "-jc",
            help=tr_multi(
                "Krei jarcent-eniron",
                "Create century entry",
                "Créer une entrée de siècle",
            ),
        ),
        bce: bool = typer.Option(
            False,
            "--bce",
            help=tr_multi(
                "Antaŭ Kristo (a.K.E.)",
                "BCE / Before Common Era",
                "Av. J.-C. / avant l'ère commune",
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
                "Montri la aldonitan nodon post konservado",
                "Show the added entry after saving",
                "Afficher l'entrée ajoutée après sauvegarde",
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
        """Aldoni novan nodon el .enc dosiero aŭ krei temp-eniron."""
        if kopii and semantika_kopii:
            error(tr_multi(
                "Uzu nur unu el --kopii aŭ --semantika-kopii.",
                "Use only one of --kopii or --semantika-kopii.",
                "Utilisez un seul de --kopii ou --semantika-kopii.",
            ))
            raise typer.Exit(1)

        if html and not vidi:
            vidi = True

        has_time = _validate_time_args(jaro, jardeko, jarcento)

        # At least one input method required
        if not dosiero and not has_time:
            error(tr_multi(
                "Bezonatas .enc dosiero aŭ temp-optiono (--jaro/--jardeko/--jarcento).",
                "Require .enc file or time option (--jaro/--jardeko/--jarcento).",
                "Fichier .enc ou option temporelle requise (--jaro/--jardeko/--jarcento).",
            ))
            raise typer.Exit(1)

        extra_fields: dict = {}
        if dosiero:
            path = Path(dosiero).expanduser().resolve()
            if not path.exists():
                error(tr_multi(
                    f"Dosiero ne trovita: {path}",
                    f"File not found: {path}",
                    f"Fichier non trouvé: {path}",
                ))
                raise typer.Exit(1)
            if not path.is_file():
                error(tr_multi(
                    f"Ne estas dosiero: {path}",
                    f"Not a file: {path}",
                    f"Ce n'est pas un fichier: {path}",
                ))
                raise typer.Exit(1)

            from A_encik.enc_format import parse_enc_file, validate_enc_entry
            try:
                parsed = parse_enc_file(path)
            except ValueError as exc:
                error(str(exc))
                raise typer.Exit(1)
            errors = validate_enc_entry(parsed)
            if errors:
                for e in errors:
                    error(f"Validiga eraro: {e}")
                raise typer.Exit(1)
            extra_fields = parsed

        service = get_service()

        if jaro is not None:
            try:
                entry = service.ensure_year(jaro, bce=bce, extra_fields=extra_fields or None)
            except ValueError as exc:
                error(str(exc))
                raise typer.Exit(1)
            msg = tr_multi(f"Aldonis jaron {jaro}", f"Added year {jaro}", f"Ajouté année {jaro}")
        elif jardeko is not None:
            try:
                entry = service.ensure_decade(jardeko, bce=bce, extra_fields=extra_fields or None)
            except ValueError as exc:
                error(str(exc))
                raise typer.Exit(1)
            msg = tr_multi(f"Aldonis jardekon {jardeko}", f"Added decade {jardeko}", f"Ajouté décennie {jardeko}")
        elif jarcento is not None:
            try:
                entry = service.ensure_century(jarcento, bce=bce, extra_fields=extra_fields or None)
            except ValueError as exc:
                error(str(exc))
                raise typer.Exit(1)
            msg = tr_multi(f"Aldonis jarcenton {jarcento}", f"Added century {jarcento}", f"Ajouté siècle {jarcento}")
        else:
            # Standard .enc file import
            assert dosiero is not None  # guaranteed by validation above
            path = Path(dosiero).expanduser().resolve()
            from A_encik.enc_format import parse_enc_file, validate_enc_entry
            try:
                parsed = parse_enc_file(path)
            except ValueError as exc:
                error(str(exc))
                raise typer.Exit(1)
            errors = validate_enc_entry(parsed)
            if errors:
                for e in errors:
                    error(f"Validiga eraro: {e}")
                raise typer.Exit(1)

            existing = service.find_by_titolo(parsed["titolo"])
            if existing:
                error(tr_multi(
                    f"Eniro '{parsed['titolo']}' jam ekzistas (#{existing['uuid'][:8]}).",
                    f"Entry '{parsed['titolo']}' already exists (#{existing['uuid'][:8]}).",
                    f"Entrée '{parsed['titolo']}' existe déjà (#{existing['uuid'][:8]}).",
                ))
                answer = typer.prompt(
                    tr_multi("Ĉu ĝisdatigi? (J/n)", "Update? (J/n)", "Mettre à jour ? (J/n)"),
                    default="J",
                )
                if answer.strip().lower() not in {"j", "jes", "y", "yes", ""}:
                    info(tr_multi("Nuligita.", "Cancelled.", "Annulé."))
                    return
                entry = service.update(existing["uuid"], parsed)
                msg = tr_multi(
                    f"Anstataŭigis {parsed['titolo']}",
                    f"Replaced {parsed['titolo']}",
                    f"Remplacé {parsed['titolo']}",
                )
            else:
                entry = service.create(parsed)
                msg = tr_multi(
                    f"Aldonis {parsed['titolo']}",
                    f"Added {parsed['titolo']}",
                    f"Ajoute {parsed['titolo']}",
                )

        info(msg)
        console.print(f"[green]UUID:[/] {entry.get('uuid')}")

        if kopii or semantika_kopii:
            if kopii:
                copy_to_clipboard(f"#{entry['uuid'][:8]}")
            if semantika_kopii:
                copy_entry_reference(entry, semantika=True)

        if vidi:
            if html:
                from A_encik.display import preview_entry
                preview_entry(entry, open_browser=True)
                info(tr_multi(
                    "Malfermis en retumilo",
                    "Opened in browser",
                    "Ouvert dans le navigateur",
                ))
            else:
                display_entry_panel(entry)
