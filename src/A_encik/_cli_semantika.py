"""Semantika sub-typer: dynamic group commands, serci, aldoni."""

from __future__ import annotations

from typing import Optional

import typer

from A import error, info
from A.console import console
from A import tr_multi

from A_encik.semantika import (
    SEMANTIKA_HELPO_TEKSTO,
    load_semantika_groups,
    normalize_semantika_add_id,
    normalize_semantika_group_name,
    write_semantika_group_rows,
)
from A_encik.semantika.wikidata import (
    semantika_search_languages,
    wikidata_property_metadata,
    wikidata_search_properties,
)

semantika_app = typer.Typer(
    name="semantika",
    help=SEMANTIKA_HELPO_TEKSTO,
    no_args_is_help=False,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)

_REGISTERED_GROUP_COMMANDS: set[str] = set()


def _print_semantika_kategorio(kategorio: str) -> None:
    """Print semantic links in a category."""
    groups = load_semantika_groups()
    rows = groups.get(kategorio)
    if not rows:
        error(tr_multi(f"Nekonata semantika grupo: {kategorio!r}", f"Unknown semantika group: {kategorio!r}", f"Groupe semantika inconnu : {kategorio!r}"))
        raise typer.Exit(1)
    info(tr_multi(f"Semantikaj ligiloj — {kategorio}", f"Semantic links — {kategorio}", f"Liens semantiques — {kategorio}"))
    for row in rows:
        ligilo = str(row.get("ligilo") or "")
        priskribo = str(row.get("priskribo") or "")
        aliases = [str(a) for a in (row.get("aliasoj") or [])]
        alias_text = ", ".join(aliases[:5]) if aliases else "-"
        if len(aliases) > 5:
            alias_text += ", ..."
        console.print(f"  [cyan]{ligilo}[/]")
        console.print(f"    {priskribo} [dim]({alias_text})[/dim]")


def _register_semantika_group_commands() -> None:
    """Dynamically register one command per group CSV file."""
    groups = load_semantika_groups()
    for group_name in sorted(groups.keys()):
        if group_name in {"serci", "aldoni"} or group_name in _REGISTERED_GROUP_COMMANDS:
            continue
        help_text = tr_multi(
            f"Montri semantikajn ligilojn de grupo '{group_name}'.",
            f"Show semantic links of group '{group_name}'.",
            f"Afficher les liens sémantiques du groupe '{group_name}'.",
        )

        def _make_cmd(g: str = group_name) -> None:
            _print_semantika_kategorio(g)

        semantika_app.command(group_name, help=help_text)(_make_cmd)
        _REGISTERED_GROUP_COMMANDS.add(group_name)


@semantika_app.callback(invoke_without_command=True)
def _semantika_root(ctx: typer.Context) -> None:
    _register_semantika_group_commands()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@semantika_app.command("serci")
def semantika_ligilo_serci(
    demando: str = typer.Argument(
        ...,
        help=tr_multi("Requête de recherche pour LIGILO/PRISKRIBO/ALIAZOJ", "Search query for LIGILO/PRISKRIBO/ALIAZOJ", "Search query for LIGILO/PRISKRIBO/ALIAZOJ"),
    ),
    lingvo: Optional[str] = typer.Option(
        None, "-l", "--lingvo",
        help=tr_multi("Code(s) de langue pour la recherche Wikidata (ex: eo,en)", "Language code(s) for Wikidata search (e.g. eo,en)", "Code(s) de langue pour la recherche Wikidata (ex: eo,en)"),
    ),
) -> None:
    """Search Wikidata for semantic link types."""
    needle = demando.strip().lower()
    if not needle:
        error(tr_multi("Mankas serĉdemando.", "Missing search query.", "Requête de recherche manquante."))
        raise typer.Exit(1)
    try:
        languages = semantika_search_languages(lingvo)
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(1) from exc

    local_matches: list[dict[str, object]] = []
    for group_name, rows in load_semantika_groups().items():
        for row in rows:
            ligilo = str(row.get("ligilo") or "")
            priskribo = str(row.get("priskribo") or "")
            aliases = [str(a) for a in (row.get("aliasoj") or [])]
            haystack = [ligilo, priskribo, *aliases]
            if any(needle in value.lower() for value in haystack if value):
                local_matches.append({
                    "fonto": "loka",
                    "grupo": group_name,
                    "ligilo": ligilo,
                    "priskribo": priskribo,
                    "aliasoj": aliases,
                })

    wikidata_matches: list[dict[str, object]] = []
    wikidata_warning = ""
    try:
        wikidata_matches = wikidata_search_properties(demando, languages)
    except RuntimeError as exc:
        wikidata_warning = str(exc)

    if not local_matches and not wikidata_matches:
        info(tr_multi("Neniuj rezultoj.", "No results.", "Aucun résultat."))
        if wikidata_warning:
            info(f"[dim]{wikidata_warning}[/dim]")
        return

    if local_matches:
        info(tr_multi("Lokaj rezultoj:", "Local results:", "Résultats locaux :"))
        for m in local_matches:
            ligilo = str(m.get("ligilo") or "")
            priskribo = str(m.get("priskribo") or "")
            grupo = str(m.get("grupo") or "")
            aliases = ", ".join(str(a) for a in (m.get("aliasoj") or []))
            console.print(f"  [cyan]{ligilo}[/] — {priskribo}")
            if aliases:
                console.print(f"    [dim]aliazoj: {aliases} (grupo: {grupo})[/dim]")

    if wikidata_matches:
        info(tr_multi("Wikidata rezultoj:", "Wikidata results:", "Résultats Wikidata :"))
        for m in wikidata_matches:
            ligilo = str(m.get("ligilo") or "")
            etikedo = str(m.get("etikedo") or "")
            priskribo = str(m.get("priskribo") or "")
            aliases = ", ".join(str(a) for a in (m.get("aliasoj") or []))
            console.print(f"  [cyan]{ligilo}[/] — {etikedo}")
            if priskribo:
                console.print(f"    {priskribo}")
            if aliases:
                console.print(f"    [dim]aliazoj: {aliases}[/dim]")

    if wikidata_warning:
        info(f"[dim]{wikidata_warning}[/dim]")


@semantika_app.command("aldoni")
def semantika_ligilo_aldoni(
    identigilo: str = typer.Argument(..., help=tr_multi("Lien ou ID Wikidata (ex: P1082 ou wdt:P1082)", "Link or Wikidata ID (e.g. P1082 or wdt:P1082)", "Lien ou ID Wikidata (ex: P1082 ou wdt:P1082)")),
    grupo: str = typer.Argument(..., help=tr_multi("Groupe cible (nom du fichier CSV)", "Target group (CSV file name)", "Groupe cible (nom du fichier CSV)")),
    priskribo: Optional[str] = typer.Option(None, "-p", "--priskribo", help=tr_multi("Description manuelle pour le repli hors ligne", "Manual description for offline fallback", "Description manuelle pour le repli hors ligne")),
    aliazoj: Optional[str] = typer.Option(None, "-a", "--aliazoj", help=tr_multi("Alias manuels (CSV) pour le repli hors ligne", "Manual aliases (CSV) for offline fallback", "Alias manuels (CSV) pour le repli hors ligne")),
    lingvo: Optional[str] = typer.Option(None, "-l", "--lingvo", help=tr_multi("Code(s) de langue pour les métadonnées Wikidata", "Language code(s) for Wikidata metadata", "Code(s) de langue pour les métadonnées Wikidata")),
) -> None:
    """Add a semantic link type to a group.

    Validates against Wikidata when possible; falls back to offline mode.
    """
    try:
        group_name = normalize_semantika_group_name(grupo)
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(1) from exc

    ligilo, prop_id = normalize_semantika_add_id(identigilo)
    groups = load_semantika_groups()

    if group_name not in groups:
        answer = typer.prompt(
            tr_multi(
                f"Grupo '{group_name}' ne ekzistas. Ĉu krei ĝin? (j/N)",
                f"Group '{group_name}' doesn't exist. Create it? (j/N)",
                f"Le groupe '{group_name}' n'existe pas. Créer ? (j/N)",
            ),
            default="n",
        )
        if answer.strip().lower() not in {"j", "jes", "y", "yes"}:
            info(tr_multi("Nuligita.", "Cancelled.", "Annulé."))
            return
        groups[group_name] = []

    rows = [dict(row) for row in groups.get(group_name, [])]
    existing_index = next(
        (i for i, row in enumerate(rows) if str(row.get("ligilo") or "").strip().lower() == ligilo.lower()),
        None,
    )
    overwrite_existing = False
    if existing_index is not None:
        info(tr_multi(f"Averto: {ligilo} jam ekzistas en grupo '{group_name}'.", f"Warning: {ligilo} already exists in group '{group_name}'.", f"Attention : {ligilo} existe déjà dans le groupe '{group_name}'."))
        answer = typer.prompt(
            tr_multi("Ĉu anstataŭigi? (j/N)", "Replace? (j/N)", "Remplacer ? (j/N)"),
            default="n",
        )
        if answer.strip().lower() not in {"j", "jes", "y", "yes"}:
            info(tr_multi("Nuligita.", "Cancelled.", "Annulé."))
            return
        overwrite_existing = True

    resolved_desc = priskribo or ""
    resolved_aliases = _parse_semantika_aliazoj(aliazoj or "")
    if prop_id and not resolved_desc:
        try:
            languages = semantika_search_languages(lingvo)
            meta = wikidata_property_metadata(prop_id, languages)
            if str(meta.get("priskribo") or "").strip():
                resolved_desc = str(meta.get("priskribo") or "").strip()
            meta_aliases = [str(v) for v in (meta.get("aliasoj") or []) if str(v)]
            for alias in meta_aliases:
                if alias.lower() not in {a.lower() for a in resolved_aliases}:
                    resolved_aliases.append(alias)
        except RuntimeError as exc:
            if not priskribo:
                error(tr_multi(
                    f"Averto: {exc}. Uzu --priskribo por offline aldono.",
                    f"Warning: {exc}. Use --priskribo for offline add.",
                    f"Attention : {exc}. Utilisez --priskribo pour l'ajout hors ligne.",
                ))
                raise typer.Exit(1) from exc

    new_row = {"ligilo": ligilo, "priskribo": resolved_desc, "aliasoj": resolved_aliases}
    if overwrite_existing and existing_index is not None:
        rows[existing_index] = new_row
    else:
        rows.append(new_row)
    write_semantika_group_rows(group_name, rows)
    from A_encik.semantika.config import invalidate_config_cache
    invalidate_config_cache()
    _register_semantika_group_commands()

    info(tr_multi(f"Aldonis {ligilo} al grupo '{group_name}'.", f"Added {ligilo} to group '{group_name}'.", f"Ajouté {ligilo} au groupe '{group_name}'."))


def _parse_semantika_aliazoj(raw: str) -> list[str]:
    """Parse comma-separated alias string."""
    return [token.strip() for token in str(raw or "").split(",") if token.strip()]


def _display_semantika_match(entry: dict) -> None:
    """Display a single semantic search match inline."""
    uuid = entry.get("uuid", "")
    titolo = entry.get("titolo", "")
    console.print(f"[bold cyan]UUID:[/] {uuid}")
    console.print(f"[bold cyan]Titolo:[/] {titolo}")
    semantikaj = entry.get("semantika", [])
    if semantikaj:
        console.print("[bold cyan]Semantiko:[/]")
        for item in (semantikaj if isinstance(semantikaj, list) else []):
            if isinstance(item, dict):
                tipo = item.get("tipo", "")
                arko = item.get("arko", "")
                valoro = item.get("valoro", "")
                unuo = item.get("unuo", "")
                line = f"  {tipo} {arko} = {valoro}"
                if unuo:
                    line += f" [{unuo}]"
                console.print(line)
