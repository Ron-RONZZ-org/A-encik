"""Grupo sub-typer for semantika — group-level CRUD commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.box import SIMPLE as BOX_SIMPLE
from rich.table import Table

from A import error, info
from A.console import console
from A import tr_multi

from A_encik.semantika import (
    create_semantika_group,
    delete_semantika_group,
    load_semantika_groups,
    normalize_semantika_group_name,
    rename_semantika_group,
)
from A_encik.semantika.config import semantika_group_file

grupo_app = typer.Typer(
    name="grupo",
    help=tr_multi(
        "Administri semantikajn grupojn.",
        "Manage semantika groups.",
        "Gérer les groupes sémantiques.",
    ),
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)


@grupo_app.command("ls")
def grupo_ls() -> None:
    """List all semantika groups with row counts and file paths."""
    groups = load_semantika_groups()
    if not groups:
        info(tr_multi("Neniuj grupoj.", "No groups.", "Aucun groupe."))
        return

    table = Table(
        title=tr_multi("Semantikaj grupoj", "Semantika groups", "Groupes sémantiques"),
        show_header=True,
        header_style="bold",
        expand=False,
        box=BOX_SIMPLE,
    )
    table.add_column(tr_multi("Grupo", "Group"), style="cyan", no_wrap=True)
    table.add_column(tr_multi("Eniroj", "Entries"), justify="right")
    table.add_column(tr_multi("Dosiero", "File"))
    for name in sorted(groups.keys()):
        path = semantika_group_file(name)
        rows = groups[name]
        table.add_row(name, str(len(rows)), str(path))
    console.print(table)


@grupo_app.command("vidi")
def grupo_vidi(
    name: str = typer.Argument(
        ...,
        help=tr_multi(
            "Nomo de grupo",
            "Group name",
            "Nom du groupe",
        ),
    ),
) -> None:
    """Show entries in a semantika group."""
    groups = load_semantika_groups()
    rows = groups.get(name)
    if not rows:
        error(tr_multi(
            f"Nekonata semantika grupo: {name!r}",
            f"Unknown semantika group: {name!r}",
            f"Groupe semantika inconnu : {name!r}",
        ))
        raise typer.Exit(1)
    table = Table(
        title=tr_multi(
            f"Semantikaj ligiloj — {name}",
            f"Semantic links — {name}",
            f"Liens sémantiques — {name}",
        ),
        show_header=True,
        header_style="bold",
        expand=False,
        box=BOX_SIMPLE,
    )
    table.add_column("LIGILO", style="cyan", no_wrap=True)
    table.add_column(tr_multi("PRISKRIBO", "Description"), style="white")
    table.add_column(tr_multi("ALIAZOJ", "Aliases"))
    for row in rows:
        ligilo = str(row.get("ligilo") or "")
        priskribo = str(row.get("priskribo") or "") or "-"
        aliases = [str(a) for a in (row.get("aliasoj") or [])]
        alias_text = ", ".join(aliases[:5]) if aliases else "-"
        if len(aliases) > 5:
            alias_text += ", ..."
        table.add_row(ligilo, priskribo, alias_text)
    console.print(table)
    info(tr_multi(
        "Uzo: en `ligilo` uzu UUID:semantiko (ekz: 1234abcd:rdf:type).",
        "Usage: in `ligilo` use UUID:semantika (e.g. 1234abcd:rdf:type).",
        "Utilisation : dans `ligilo` utiliser UUID:semantiko (ex: 1234abcd:rdf:type).",
    ))


@grupo_app.command("aldoni")
def grupo_aldoni(
    name: str = typer.Argument(
        ...,
        help=tr_multi(
            "Nomo de nova grupo",
            "Name of new group",
            "Nom du nouveau groupe",
        ),
    ),
) -> None:
    """Create a new empty semantika group."""
    try:
        path = create_semantika_group(name)
        info(tr_multi(
            f"Kreis grupon '{path.stem}'.",
            f"Created group '{path.stem}'.",
            f"Groupe '{path.stem}' créé.",
        ))
    except (ValueError, FileExistsError) as exc:
        error(str(exc))
        raise typer.Exit(1)


@grupo_app.command("modifi")
def grupo_modifi(
    old_name: str = typer.Argument(
        ...,
        help=tr_multi(
            "Nuna nomo de grupo",
            "Current group name",
            "Nom actuel du groupe",
        ),
    ),
    new_name: str = typer.Argument(
        ...,
        help=tr_multi(
            "Nova nomo de grupo",
            "New group name",
            "Nouveau nom du groupe",
        ),
    ),
) -> None:
    """Rename a semantika group (renames its CSV file)."""
    try:
        path = rename_semantika_group(old_name, new_name)
        info(tr_multi(
            f"Renomis grupon '{old_name}' al '{path.stem}'.",
            f"Renamed group '{old_name}' to '{path.stem}'.",
            f"Groupe '{old_name}' renommé en '{path.stem}'.",
        ))
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        error(str(exc))
        raise typer.Exit(1)


@grupo_app.command("forigi")
def grupo_forigi(
    name: str = typer.Argument(
        ...,
        help=tr_multi(
            "Nomo de grupo",
            "Group name",
            "Nom du groupe",
        ),
    ),
    konfirmi: bool = typer.Option(
        False,
        "--jes",
        "-y",
        help=tr_multi(
            "Konfirmi sen demande",
            "Confirm without prompt",
            "Confirmer sans demande",
        ),
    ),
) -> None:
    """Delete a semantika group and all its links."""
    try:
        normalized = normalize_semantika_group_name(name)
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(1)

    if not konfirmi:
        info(tr_multi(
            f"Forigos grupon '{normalized}' kaj ĉiujn ĝiajn ligilojn.",
            f"Will delete group '{normalized}' and all its links.",
            f"Suppression du groupe '{normalized}' et tous ses liens.",
        ))
        answer = typer.prompt(
            tr_multi(
                "Ĉu daŭrigi? (j/N)",
                "Continue? (j/N)",
                "Continuer ? (j/N)",
            ),
            default="n",
        )
        if answer.strip().lower() not in {"j", "jes", "y", "yes"}:
            info(tr_multi("Nuligita.", "Cancelled.", "Annulé."))
            return

    try:
        delete_semantika_group(normalized)
        info(tr_multi(
            f"Forigis grupon '{normalized}'.",
            f"Deleted group '{normalized}'.",
            f"Groupe '{normalized}' supprimé.",
        ))
    except FileNotFoundError as exc:
        error(str(exc))
        raise typer.Exit(1)
