"""CLI for encik command — creates the main Typer app and registers all sub-typers."""

from __future__ import annotations

import typer

from A import tr_multi

app = typer.Typer(
    name="encik",
    help=tr_multi(
        "Encik — enciklopedio kaj konada micro-apo.",
        "Encik — encyclopedia and knowledge micro-app.",
        "Encik — micro-application encyclopédie et connaissance.",
    ),
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)

# Register top-level commands (CRUD, aldoni, search, special)
from A_encik._cli_crud import register_commands as _register_crud
from A_encik._cli_aldoni import register_commands as _register_aldoni
from A_encik._cli_search import register_commands as _register_search
from A_encik._cli_special import register_commands as _register_special

_register_crud(app)
_register_aldoni(app)
_register_search(app)
_register_special(app)

# Register rubujo sub-typer
from A_encik._cli_rubujo import rubujo_app  # noqa: E402

app.add_typer(rubujo_app, name="rubujo")

# Register semantika sub-typer
from A_encik._cli_semantika import semantika_app  # noqa: E402

app.add_typer(semantika_app, name="semantika")

__all__ = ["app"]
