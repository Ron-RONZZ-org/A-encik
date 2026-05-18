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
        cio: bool = typer.Option(
            False,
            "--cio",
            "-a",
            help=tr_multi(
                "Ankaŭ rekonstrui ligilo kaj terminologio por ĉiuj eniroj",
                "Also rebuild ligilo and terminologio for ALL entries",
                "Reconstruire aussi ligilo et terminologio pour TOUTES les entrées",
            ),
        ),
        latex: bool = typer.Option(
            False,
            "--latex",
            "-l",
            help=tr_multi(
                "Ripari manĝitajn LaTeX-eskapojn (tab anstataŭ \\t)",
                "Fix mangled LaTeX escapes (tab instead of \\t)",
                "Corriger les échappements LaTeX corrompus (tab au lieu de \\t)",
            ),
        ),
    ) -> None:
        """Reconcile all bidirectional semantic links in the database.

        Without --cio: only syncs reverse superklaso→ligilo links.
        With --cio: also rebuilds ligilo from inline refs and
        terminologio_search from terminologio for every entry.
        With --latex: fix mangled LaTeX escapes (tab/newline → \\t/\\n)
        in existing entries imported with the old buggy parser.
        """
        service = get_service()
        count = service.reconcile_all_reverse_links()

        if latex:
            fixed = service.fix_latex_escapes()
            info(tr_multi(
                f"Riparis {fixed} eniro(j)n kun manĝitaj LaTeX-eskapoj.",
                f"Fixed {fixed} entr(ies) with mangled LaTeX escapes.",
                f"Corrigé {fixed} entrée(s) avec échappements LaTeX corrompus.",
            ))

        if cio:
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
    def generi(
        prompto: str = typer.Argument(
            ...,
            help=tr_multi(
                "Temo aŭ priskribo por la enhavo",
                "Topic or description for the content",
                "Sujet ou description du contenu",
            ),
        ),
        provizanto: Optional[str] = typer.Option(
            None,
            "--provizanto",
            "-p",
            help=tr_multi(
                "Provizanto (vidu 'agento agordi ls')",
                "Provider (see 'agento agordi ls')",
                "Fournisseur (voir 'agento agordi ls')",
            ),
        ),
        konservi: Optional[Path] = typer.Option(
            None,
            "--konservi",
            "-K",
            help=tr_multi(
                "Dosiero por konservi la rezulton (ekz: eligo.enc)",
                "File path to save the result (e.g. output.enc)",
                "Chemin du fichier pour sauvegarder le r\u00e9sultat (ex: sortie.enc)",
            ),
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            "-v",
            help=tr_multi(
                "Montri la plenan konversacion kun LLM",
                "Show full LLM conversation",
                "Afficher la conversation compl\u00e8te avec LLM",
            ),
        ),
    ) -> None:
        """Generate a .enc knowledge entry using AI (via A-agento).

        Uses the configured LLM provider to generate an .enc formatted
        knowledge entry. Requires A-agento to be installed.

        Examples:
            encik generi "macOS"
            encik generi "Python" --konservi eligo.enc
            encik generi "Grokipedia" --verbose
        """
        try:
            from A_agento.commands.knowledge import generi as _agento_generi
        except ImportError:
            error(tr_multi(
                "Bezonas A-agento por AI-generado.",
                "A-agento is required for AI generation.",
                "A-agento est requis pour la g\u00e9n\u00e9ration IA.",
            ))
            from A.utils.deps import ensure_dependency
            try:
                ensure_dependency("A_agento", "A-agento")
            except ImportError:
                error(tr_multi(
                    "Ne povis instali A-agento. Instalu permane: uv pip install A-agento",
                    "Could not install A-agento. Install manually: uv pip install A-agento",
                    "Impossible d'installer A-agento. Installez manuellement : uv pip install A-agento",
                ))
                raise typer.Exit(1) from None
            # Retry after installation
            from A_agento.commands.knowledge import generi as _agento_generi  # noqa: F811

        _agento_generi(
            prompto=prompto,
            formato="enc",
            titolo=None,
            provizanto=provizanto,
            konservi=konservi,
            kopii=False,
            verbose=verbose,
            interjekti=False,
        )
