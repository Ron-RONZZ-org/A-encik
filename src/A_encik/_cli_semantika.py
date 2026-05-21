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

from A_encik._cli_semantika_grupo import grupo_app

semantika_app = typer.Typer(
    name="semantika",
    help=SEMANTIKA_HELPO_TEKSTO,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)

semantika_app.add_typer(grupo_app, name="grupo")


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
        from rich.table import Table
        from rich.box import SIMPLE as BOX_SIMPLE
        table = Table(
            title=tr_multi(
                "Lokaj rezultoj",
                "Local results",
                "Résultats locaux",
            ),
            show_header=True,
            header_style="bold cyan",
            box=BOX_SIMPLE,
            expand=False,
        )
        table.add_column("ID", style="cyan", no_wrap=True, width=16)
        table.add_column(tr_multi("Priskribo", "Description", "Description"))
        table.add_column(tr_multi("Grupo", "Group", "Groupe"))
        table.add_column(tr_multi("Aliazoj", "Aliases", "Alias"), width=30)
        for m in local_matches:
            ligilo = str(m.get("ligilo") or "")
            priskribo = str(m.get("priskribo") or "-")
            grupo = str(m.get("grupo") or "-")
            aliases = ", ".join(str(a) for a in (m.get("aliasoj") or [])[:3])
            if len((m.get("aliasoj") or [])) > 3:
                aliases += ", ..."
            table.add_row(ligilo, priskribo, grupo, aliases or "-")
        console.print(table)

    if wikidata_matches:
        from rich.table import Table
        from rich.box import SIMPLE as BOX_SIMPLE
        table = Table(
            title=tr_multi(
                "Wikidata rezultoj",
                "Wikidata results",
                "Résultats Wikidata",
            ),
            show_header=True,
            header_style="bold cyan",
            box=BOX_SIMPLE,
            expand=False,
        )
        table.add_column("ID", style="cyan", no_wrap=True, width=16)
        table.add_column(tr_multi("Etikedo", "Label", "Étiquette"))
        table.add_column(tr_multi("Priskribo", "Description", "Description"))
        table.add_column(tr_multi("Aliazoj", "Aliases", "Alias"), width=30)
        for m in wikidata_matches:
            ligilo = str(m.get("ligilo") or "")
            etikedo = str(m.get("etikedo") or "-")
            priskribo = str(m.get("priskribo") or "-")
            aliase = ", ".join(str(a) for a in (m.get("aliasoj") or [])[:3])
            if len((m.get("aliasoj") or [])) > 3:
                aliase += ", ..."
            table.add_row(ligilo, etikedo, priskribo, aliase or "-")
        console.print(table)

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

    info(tr_multi(f"Aldonis {ligilo} al grupo '{group_name}'.", f"Added {ligilo} to group '{group_name}'.", f"Ajouté {ligilo} au groupe '{group_name}'."))


@semantika_app.command("forigi")
def semantika_ligilo_forigi(
    identigilo: str = typer.Argument(
        ..., help=tr_multi("Ligilo aŭ Wikidata ID (ex: P1082)", "Link or Wikidata ID (e.g. P1082)", "Lien ou ID Wikidata (ex: P1082)"),
    ),
    grupo: str = typer.Argument(
        ..., help=tr_multi("Nomo de grupo", "Group name", "Nom du groupe"),
    ),
    konfirmi: bool = typer.Option(
        False, "--jes", "-y", help=tr_multi("Konfirmi sen demande", "Confirm without prompt", "Confirmer sans demande"),
    ),
) -> None:
    """Delete a semantic link from a group."""
    try:
        group_name = normalize_semantika_group_name(grupo)
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(1) from exc

    ligilo, _prop_id = normalize_semantika_add_id(identigilo)
    groups = load_semantika_groups()

    if group_name not in groups:
        error(tr_multi(
            f"Grupo '{group_name}' ne ekzistas.",
            f"Group '{group_name}' does not exist.",
            f"Le groupe '{group_name}' n'existe pas.",
        ))
        raise typer.Exit(1)

    rows = groups[group_name]
    idx = next(
        (i for i, row in enumerate(rows) if str(row.get("ligilo") or "").strip().lower() == ligilo.lower()),
        None,
    )
    if idx is None:
        error(tr_multi(
            f"Ligilo {ligilo} ne trovitas en grupo '{group_name}'.",
            f"Link {ligilo} not found in group '{group_name}'.",
            f"Lien {ligilo} non trouvé dans le groupe '{group_name}'.",
        ))
        raise typer.Exit(1)

    if not konfirmi:
        priskribo = str(rows[idx].get("priskribo") or "")
        info(tr_multi(
            f"Forigos: {ligilo} — {priskribo} (el grupo '{group_name}')",
            f"Will delete: {ligilo} — {priskribo} (from group '{group_name}')",
            f"Suppression : {ligilo} — {priskribo} (du groupe '{group_name}')",
        ))
        answer = typer.prompt(
            tr_multi("Ĉu daŭrigi? (j/N)", "Continue? (j/N)", "Continuer ? (j/N)"),
            default="n",
        )
        if answer.strip().lower() not in {"j", "jes", "y", "yes"}:
            info(tr_multi("Nuligita.", "Cancelled.", "Annulé."))
            return

    rows.pop(idx)
    write_semantika_group_rows(group_name, rows)
    from A_encik.semantika.config import invalidate_config_cache
    invalidate_config_cache()

    info(tr_multi(
        f"Forigis {ligilo} el grupo '{group_name}'.",
        f"Deleted {ligilo} from group '{group_name}'.",
        f"Supprimé {ligilo} du groupe '{group_name}'.",
    ))


@semantika_app.command("modifi")
def semantika_ligilo_modifi(
    identigilo: str = typer.Argument(
        ..., help=tr_multi("Ligilo aŭ Wikidata ID (ex: P1082)", "Link or Wikidata ID (e.g. P1082)", "Lien ou ID Wikidata (ex: P1082)"),
    ),
    grupo: str = typer.Argument(
        ..., help=tr_multi("Nomo de grupo", "Group name", "Nom du groupe"),
    ),
    priskribo: Optional[str] = typer.Option(
        None, "-p", "--priskribo", help=tr_multi("Nova priskribo", "New description", "Nouvelle description"),
    ),
    aliazoj: Optional[str] = typer.Option(
        None, "-a", "--aliazoj", help=tr_multi("Novaj aliasoj (CSV)", "New aliases (CSV)", "Nouveaux alias (CSV)"),
    ),
    refetch: bool = typer.Option(
        False, "--refetch", "-r", help=tr_multi("Refetch metadata from Wikidata", "Re-fetch metadata from Wikidata", "Re-rechercher les métadonnées Wikidata"),
    ),
    lingvo: Optional[str] = typer.Option(
        None, "-l", "--lingvo", help=tr_multi("Lingvokodoj por refetch (ex: eo,en)", "Language codes for refetch (e.g. eo,en)", "Codes de langue pour refetch (ex: eo,en)"),
    ),
) -> None:
    """Modify a semantic link in a group.

    If --refetch is given, re-fetch metadata from Wikidata (overrides manual values).
    Otherwise only fields explicitly provided via --priskribo / --aliazoj are updated.
    """
    try:
        group_name = normalize_semantika_group_name(grupo)
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(1) from exc

    ligilo, prop_id = normalize_semantika_add_id(identigilo)
    groups = load_semantika_groups()

    if group_name not in groups:
        error(tr_multi(
            f"Grupo '{group_name}' ne ekzistas.",
            f"Group '{group_name}' does not exist.",
            f"Le groupe '{group_name}' n'existe pas.",
        ))
        raise typer.Exit(1)

    rows = [dict(row) for row in groups[group_name]]
    idx = next(
        (i for i, row in enumerate(rows) if str(row.get("ligilo") or "").strip().lower() == ligilo.lower()),
        None,
    )
    if idx is None:
        error(tr_multi(
            f"Ligilo {ligilo} ne trovitas en grupo '{group_name}'.",
            f"Link {ligilo} not found in group '{group_name}'.",
            f"Lien {ligilo} non trouvé dans le groupe '{group_name}'.",
        ))
        raise typer.Exit(1)

    existing = rows[idx]

    if refetch and prop_id:
        try:
            languages = semantika_search_languages(lingvo)
            meta = wikidata_property_metadata(prop_id, languages)
            if str(meta.get("priskribo") or "").strip():
                existing["priskribo"] = str(meta.get("priskribo") or "").strip()
            meta_aliases = [str(v) for v in (meta.get("aliasoj") or []) if str(v)]
            existing_aliases = [str(a).lower() for a in (existing.get("aliasoj") or [])]
            for alias in meta_aliases:
                if alias.lower() not in existing_aliases:
                    existing.setdefault("aliasoj", []).append(alias)
        except RuntimeError as exc:
            warning = str(exc)
            info(tr_multi(
                f"Averto: {warning}. Aliaj kampoj konservitaj.",
                f"Warning: {warning}. Other fields saved.",
                f"Attention : {warning}. Autres champs sauvegardés.",
            ))

    # Apply manual overrides (these always win over refetch)
    if priskribo is not None:
        existing["priskribo"] = priskribo
    if aliazoj is not None:
        existing["aliasoj"] = _parse_semantika_aliazoj(aliazoj)

    rows[idx] = existing
    write_semantika_group_rows(group_name, rows)
    from A_encik.semantika.config import invalidate_config_cache
    invalidate_config_cache()

    info(tr_multi(
        f"Modifis {ligilo} en grupo '{group_name}'.",
        f"Modified {ligilo} in group '{group_name}'.",
        f"Modifié {ligilo} dans le groupe '{group_name}'.",
    ))


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
