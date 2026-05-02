"""Semantic link management for A-encik."""

from A_encik.semantika.config import (
    SEMANTIKA_KATEGORIOJ,
    SEMANTIKA_HELPO_TEKSTO,
    SEMANTIKA_LIGILO_DEFINOJ,
    ensure_semantika_group_files,
    load_semantika_groups,
    normalize_semantika_add_id,
    normalize_semantika_group_name,
    normalize_semantika_ligilo,
    runtime_known_semantika_ligiloj,
    semantika_group_file,
    write_semantika_group_rows,
)
from A_encik.semantika.search import (
    entry_matches_semantika_conditions,
    parse_semantika_serci_conditions,
)
from A_encik.semantika.wikidata import (
    semantika_search_languages,
    wikidata_property_metadata,
    wikidata_search_properties,
)

__all__ = [
    "SEMANTIKA_KATEGORIOJ",
    "SEMANTIKA_HELPO_TEKSTO",
    "SEMANTIKA_LIGILO_DEFINOJ",
    "ensure_semantika_group_files",
    "load_semantika_groups",
    "normalize_semantika_add_id",
    "normalize_semantika_group_name",
    "normalize_semantika_ligilo",
    "runtime_known_semantika_ligiloj",
    "semantika_group_file",
    "write_semantika_group_rows",
    "entry_matches_semantika_conditions",
    "parse_semantika_serci_conditions",
    "semantika_search_languages",
    "wikidata_property_metadata",
    "wikidata_search_properties",
]
