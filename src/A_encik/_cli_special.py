"""Other commands: grafo, repacigi, eksporti, importi, agordi, generi."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from A import error, info
from A.console import console
from A import tr_multi

from A_encik.service import get_service
from A_encik.display_helpers import entry_display_name


def register_commands(app: typer.Typer) -> None:
    """Register special commands on the given Typer app."""

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
            help=tr_multi("Maksimuma profundeco", "Maximum depth", "Profondeur maximale"),
        ),
    ) -> None:
        """Show knowledge graph for an entry."""
        service = get_service()

        entry = service.get(ref)
        if not entry:
            entry = service.find_by_titolo(ref)
        if not entry:
            matches = service.find_by_uuid_prefix(ref)
            if len(matches) == 1:
                entry = matches[0]

        if not entry:
            error(tr_multi(f"Encik {ref} ne trovitas", f"Entry {ref} not found", f"Entrée {ref} non trouvée"))
            raise typer.Exit(1)

        graph = service.get_linked_graph(entry["uuid"], max_depth=profundeco)

        console.print(f"[bold]Grafo por:[/bold] {entry_display_name(entry)}")
        console.print()

        if not graph["nodes"]:
            info(tr_multi("Neniuj ligiloj", "No links", "Aucun lien"))
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
    def repacigi(
        cxio: bool = typer.Option(
            False,
            "--cxio",
            "-a",
            help=tr_multi(
                "Ankaŭ rekonstrui ligilo kaj terminologio por ĈIUJ eniroj",
                "Also rebuild ligilo and terminologio for ALL entries",
                "Reconstruire aussi ligilo et terminologio pour TOUTES les entrées",
            ),
        ),
    ) -> None:
        """Reconcile all bidirectional semantic links in the database.

        Without --cxio: only syncs reverse superklaso→ligilo links.
        With --cxio: also rebuilds ligilo from inline refs and
        terminologio_search from terminologio for every entry.
        """
        service = get_service()
        count = service.reconcile_all_reverse_links()

        if cxio:
            rebuilt = service.reconcile_all_computed_fields()
            info(tr_multi(
                f"Repacigis {count} ligilojn, rekonstruis {rebuilt} enirojn",
                f"Reconciled {count} links, rebuilt {rebuilt} entries",
                f"Réconcilié {count} liens, reconstruit {rebuilt} entrées",
            ))
        else:
            info(tr_multi(
                f"Repacigis {count} ligilojn",
                f"Reconciled {count} links",
                f"Réconcilié {count} liens",
            ))

    @app.command("eksporti")
    def eksporti(
        ref: str = typer.Argument(
            ...,
            help=tr_multi("UUID aŭ titolo", "UUID or title", "UUID ou titre"),
        ),
        celvojo: str = typer.Argument(
            ...,
            help=tr_multi("Eliga dosiero", "Output file", "Fichier de sortie"),
        ),
        formato: str = typer.Option(
            "enc",
            "--format",
            "-f",
            help=tr_multi("Formato: enc aŭ json", "Format: enc or json", "Format: enc ou json"),
        ),
    ) -> None:
        """Export a knowledge entry."""
        import json

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
                    error(tr_multi("Uz pli specifan referencon", "Use a more specific reference", "Utilisez une référence plus spécifique"))
                    raise typer.Exit(1)

        if not entry:
            error(tr_multi(f"Encik {ref} ne trovitas", f"Entry {ref} not found", f"Entrée {ref} non trouvée"))
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

        n = entry_display_name(entry)
        info(tr_multi(f"Eksportis {n} al {out_path}", f"Exported {n} to {out_path}", f"Exporté {n} vers {out_path}"))

    @app.command("importi")
    def importi(
        fonto: str = typer.Argument(
            ...,
            help=tr_multi("Eniga .enc dosiero", "Input .enc file", "Fichier .enc d'entrée"),
        ),
    ) -> None:
        """Import a knowledge entry from .enc file."""
        from A_encik.enc_format import parse_enc_file, validate_enc_entry

        path = Path(fonto).expanduser()
        if not path.exists():
            error(tr_multi(f"Dosiero {fonto} ne ekzistas", f"File {fonto} does not exist", f"Fichier {fonto} n'existe pas"))
            raise typer.Exit(1)

        try:
            entry = parse_enc_file(path)
        except ValueError as exc:
            error(str(exc))
            raise typer.Exit(1)

        errors = validate_enc_entry(entry)
        if errors:
            for e in errors:
                error(f"Validiga eraro: {e}")
            raise typer.Exit(1)

        service = get_service()
        created = service.create(entry)

        n = entry_display_name(created)
        info(tr_multi(f"Importis {n}", f"Imported {n}", f"Importé {n}"))

    @app.command("agordi")
    def agordi() -> None:
        """Display current settings."""
        from A.core.config import load_config
        config = load_config()
        console.print("[bold]Encik Agordo[/bold]")
        console.print(f"  Language: {config.language}")

    @app.command("generi")
    def generi() -> None:
        """Generate entry with AI (TODO)."""
        info("[dim]TODO: implement generi - requires A-AI rewrite[/dim]")
