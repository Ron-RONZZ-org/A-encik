"""CLI for encik command."""

from __future__ import annotations

import typer

from A import info, tr

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


@app.command()
def ls() -> None:
    """List all knowledge entries."""
    info("[dim]TODO: implement list[/dim]")


@app.command()
def vidi(uuid: str) -> None:
    """View a knowledge entry."""
    info(f"[dim]TODO: implement vidi {uuid}[/dim]")


__all__ = ["app"]