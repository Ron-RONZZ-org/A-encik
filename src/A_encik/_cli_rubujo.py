"""Recycle bin (rubujo) commands."""

from __future__ import annotations

from typing import Annotated

import typer

from A import error, info
from A.console import console
from A import tr_multi

from A_encik.service import get_service

rubujo_app = typer.Typer(
    name="rubujo",
    help=tr_multi("Rubujo", "Recycle bin", "Corbeille"),
)


@rubujo_app.command("ls")
def rubujo_ls(
    limo: int = typer.Option(50, "--limo", "-n", help=tr_multi("Maksimum da ensxtoj", "Max entries to show", "Max entries to show")),
) -> None:
    """List trashed entries."""
    service = get_service()
    entries = service.get_trash(limit=limo)

    if not entries:
        info(tr_multi("Rubujo estas malplena", "Recycle bin is empty", "La corbeille est vide"))
        return

    console.print(f"[bold]{tr_multi('Rubujo', 'Recycle bin', 'Corbeille')}[/bold]")
    console.print(f"  {tr_multi('Nombro da ensxtoj:', 'Entries:', 'Entrées:')} {len(entries)}")
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

    entry = None
    for trashed in service.get_trash(limit=1000):
        if trashed.get("uuid") == ref or trashed.get("titolo") == ref:
            entry = trashed
            break

    if not entry:
        error(tr_multi(f"Eniro {ref} ne trovitas en rubujo", f"Entry {ref} not found in trash", f"Entrée {ref} non trouvée dans la corbeille"))
        raise typer.Exit(1)

    service.restore(entry["uuid"])
    info(tr_multi(f"Restaŭris {entry['titolo']}", f"Restored {entry['titolo']}", f"Restauré {entry['titolo']}"))


@rubujo_app.command("malplenigi")
def rubujo_malplenigi(
    konfirmi: bool = typer.Option(False, "--jes", "-y", help=tr_multi("Konfirmi sen demande", "Confirm without prompt", "Confirmer sans demande")),
) -> None:
    """Empty the recycle bin."""
    if not konfirmi:
        console.print(tr_multi("Uz --jes por konfirmi", "Use --jes to confirm", "Utilisez --jes pour confirmer"))
        raise typer.Exit(1)

    service = get_service()
    count = service.empty_trash()
    info(tr_multi(f"Malplenigis rubujon ({count} ensxtoj)", f"Emptied trash ({count} entries)", f"Corbeille vidée ({count} entrées)"))


@rubujo_app.command("forigi")
def rubujo_permanent_forigi(
    refs: Annotated[list[str], typer.Argument(..., help=tr_multi("UUID au titolo (pluraj)", "UUID or title (multiple)", "UUID ou titre (plusieurs)"))],
    konfirmi: bool = typer.Option(False, "--jes", "-y", help=tr_multi("Konfirmi sen demande", "Confirm without prompt", "Confirmer sans demande")),
) -> None:
    """Permanently delete entries from recycle bin."""
    if not konfirmi:
        console.print(tr_multi("Uz --jes por konfirmi", "Use --jes to confirm", "Utilisez --jes pour confirmer"))
        raise typer.Exit(1)

    service = get_service()

    entry = None
    for trashed in service.get_trash(limit=1000):
        if trashed.get("uuid") == ref or trashed.get("titolo") == ref:
            entry = trashed
            break

    if not entry:
        error(tr_multi(f"Eniro {ref} ne trovitas en rubujo", f"Entry {ref} not found in trash", f"Entrée {ref} non trouvée dans la corbeille"))
        raise typer.Exit(1)

    service.permanent_delete(entry["uuid"])
    info(tr_multi(f"Forigis {entry['titolo']} permanenta", f"Permanently deleted {entry['titolo']}", f"Supprimé {entry['titolo']} définitivement"))
