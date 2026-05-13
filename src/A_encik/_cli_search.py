"""Search commands: serci, semantika-serci."""

from __future__ import annotations

from typing import Optional

import typer

from A import error, info
from A.console import console
from A import tr_multi
from A.utils.interactive import select_candidate

from A_encik.service import get_service
from A_encik.display_helpers import (
    preferred_lang,
    entry_locale_title,
    normalize_lingvo_codes,
    print_candidates_table,
    copy_entry_reference,
)
from A_encik.display import display_entry_panel
from A_encik._cli_semantika import _display_semantika_match
from A_encik.semantika.search import parse_semantika_serci_conditions


def register_commands(app: typer.Typer) -> None:
    """Register search commands on the given Typer app."""

    @app.command("serci")
    def serci(
        demando: str | None = typer.Argument(
            None,
            help=tr_multi("Serĉa demando (titolo defaŭlte, plena teksto kun -t)", "Search query (title by default, full text with -t)", "Requête de recherche (titre par défaut, texte intégral avec -t)"),
        ),
        lingvo: str | None = typer.Option(
            None,
            "-l",
            "--lingvo",
            help=tr_multi("Preferataj lingvokodoj (komo-disigitaj). Ekz: -l fr,en", "Preferred language codes (comma-separated). Example: -l fr,en", "Codes de langue préférés (séparés par des virgules). Exemple: -l fr,en"),
        ),
        teksto: bool = typer.Option(
            False,
            "-t",
            "--teksto",
            help=tr_multi("Serĉi plenan enhavon (ne nur titolo)", "Search full content (not just title)", "Rechercher dans tout le contenu (pas seulement le titre)"),
        ),
        preciza: bool = typer.Option(
            False,
            "-p",
            "--preciza",
            help=tr_multi("Malŝalti malklaran rezervan kongruigon", "Disable fuzzy fallback matching", "Désactiver la correspondance floue de secours"),
        ),
        nova_unue: bool = typer.Option(
            False,
            "--nova-unue",
            help=tr_multi("Plej novaj rezultoj unue", "Newest results first", "Résultats les plus récents d'abord"),
        ),
        malnova_unue: bool = typer.Option(
            False,
            "--malnova-unue",
            help=tr_multi("Plej malnovaj rezultoj unue", "Oldest results first", "Résultats les plus anciens d'abord"),
        ),
        subklasoj: str | None = typer.Option(
            None,
            "-s",
            "--subklasoj",
            help=tr_multi("Serĉi subklasojn de termino (titolo aŭ UUID)", "Search subclasses of term (title or UUID)", "Rechercher les sous-classes d'un terme (titre ou UUID)"),
        ),
        superklasoj: str | None = typer.Option(
            None,
            "-S",
            "--superklasoj",
            help=tr_multi("Serĉi superklasojn de termino (titolo aŭ UUID)", "Search superclasses of term (title or UUID)", "Rechercher les super-classes d'un terme (titre ou UUID)"),
        ),
        limo: int = typer.Option(
            10,
            "-L",
            "--limo",
            help=tr_multi("Maksimumaj rezultoj (defaŭlte 10)", "Max results (default 10)", "Résultats max (10 par défaut)"),
        ),
        html: bool = typer.Option(
            False,
            "-H",
            "--html",
            help=tr_multi("Montri kiel semantikan retan diagramon en retumilo", "Display results as semantic web diagram in browser", "Afficher sous forme de diagramme web sémantique dans le navigateur"),
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
        """Search knowledge entries."""
        service = get_service()

        if kopii and semantika_kopii:
            error(tr_multi("Use only one of --kopii or --semantika-kopii", "Use only one of --kopii or --semantika-kopii", "Utilisez un seul de --kopii ou --semantika-kopii"))
            raise typer.Exit(1)

        preferred_search_langs = normalize_lingvo_codes(lingvo)

        def _preferred_search_lang(entry: dict) -> str:
            """Get best language for a single entry."""
            if preferred_search_langs:
                for lang in preferred_search_langs:
                    if entry.get("terminologio", {}).get(lang) and entry.get("difinoj", {}).get(lang):
                        return lang
            return preferred_lang(entry.get("terminologio", {}), entry.get("difinoj", {}))

        def _copy_and_show(candidates: list[dict], idx: int = 0) -> None:
            """Copy reference and display a single entry."""
            if not candidates or idx >= len(candidates):
                return
            target = candidates[idx]
            if kopii or semantika_kopii:
                copy_entry_reference(target, semantika=semantika_kopii)
            # Auto-open for KaTeX/images content
            from A_encik.display import maybe_auto_open_browser
            if maybe_auto_open_browser(target):
                return
            display_entry_panel(target, selected_lang=_preferred_search_lang(target))

        if demando is None:
            entries = service.list(order_by="kreita_je", desc=True, limit=limo)
            if not entries:
                info(tr_multi("Neniuj rezultoj", "No results", "Aucun résultat"))
                return
            print_candidates_table(entries, preferred_langs=preferred_search_langs)
            info(tr_multi(f"{len(entries)} rezultoj", f"{len(entries)} results", f"{len(entries)} résultats"))
            return

        entry = service.get(demando)
        if not entry:
            entry = service.find_by_titolo(demando)
            # If the match is accent-different (e.g. "stato" → "ŝtato"),
            # treat it as a search result, not a perfect match.
            if entry:
                from A.utils.normalize import fold_search_text as _fold
                query_lower = demando.lower()
                title_lower = entry.get("titolo", "").lower()
                _query_folded = _fold(demando)
                _title_folded = _fold(entry.get("titolo", ""))
                # Perfect match only if same lowercase (accents match)
                if query_lower != title_lower:
                    # Accent-different — push into search flow below
                    entry = None
        if not entry:
            matches = service.find_by_uuid_prefix(demando)
            if len(matches) == 1:
                entry = matches[0]

        if not entry:
            if teksto:
                entries = service.search_fts(demando, limit=limo)
            else:
                entries = service.search_like(demando, limit=limo)

            if not entries:
                info(tr_multi("Neniuj rezultoj", "No results", "Aucun résultat"))
                return

            if len(entries) == 1:
                _copy_and_show(entries)
                return

            result = select_candidate(
                entries,
                columns=[
                    {"header": "UUID", "style": "dim", "width": 10},
                    {"header": "Titolo"},
                ],
                row_formatter=lambda e, i: [
                    e.get("uuid", "")[:8],
                    entry_locale_title(e, preferred_langs=preferred_search_langs),
                ],
            )
            if result is not None:
                idx, _ = result
                _copy_and_show(entries, idx)
            return

        results: list[dict] = []
        seen_uuids: set = {entry.get("uuid")}

        if subklasoj:
            subclasses = service.get_subclasses(entry["uuid"])
            for sc in subclasses:
                if sc["entry"]["uuid"] not in seen_uuids:
                    results.append(sc["entry"])
                    seen_uuids.add(sc["entry"]["uuid"])

        if superklasoj:
            superclasses = service.get_superclasses(entry["uuid"])
            for sc in superclasses:
                if sc["entry"]["uuid"] not in seen_uuids:
                    results.append(sc["entry"])
                    seen_uuids.add(sc["entry"]["uuid"])

        if not (subklasoj or superklasoj):
            _copy_and_show([entry])
            return

        if not results:
            info(tr_multi("Neniuj rezultoj", "No results", "Aucun résultat"))
            return

        if len(results) == 1:
            _copy_and_show(results)
            return

        result = select_candidate(
            results,
            columns=[
                {"header": "UUID", "style": "dim", "width": 10},
                {"header": "Titolo"},
            ],
            row_formatter=lambda e, i: [
                e.get("uuid", "")[:8],
                entry_locale_title(e, preferred_langs=preferred_search_langs),
            ],
        )
        if result is not None:
            idx, _ = result
            _copy_and_show(results, idx)

    @app.command("semantika-serci")
    def semantika_serci(
        esprimo: str = typer.Argument(
            ...,
            help=tr_multi("wdt:P1082 (0,1000); wdt:P31 true", "Conditions separated by ';'. Examples:\n", "Conditions séparées par ';'. Exemples:\n"),
        ),
    ) -> None:
        """Search entries by semantic conditions (AND between conditions)."""
        service = get_service()

        try:
            conditions = parse_semantika_serci_conditions(esprimo)
        except ValueError as exc:
            error(str(exc))
            raise typer.Exit(1) from exc

        matches = service.search_semantika(conditions)

        if not matches:
            info(tr_multi("Neniu nodo trovita por semantika-serĉo.", "No entries found for semantic search.", "Aucune entrée trouvée pour la recherche sémantique."))
            return

        if len(matches) == 1:
            _display_semantika_match(matches[0])
            return

        info(tr_multi(f"{len(matches)} nodo(j) trovitaj.", f"{len(matches)} entry(ies) found.", f"{len(matches)} entrée(s) trouvée(s)."))
        for entry in matches:
            uuid = str(entry.get("uuid", ""))[:8]
            titolo = entry.get("titolo", "")
            console.print(f"  [cyan]{uuid}[/] {titolo}")
