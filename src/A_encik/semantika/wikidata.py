"""Backward-compatible wrapper around A.core.wikidata for A-encik.

Re-exports A-encik's original function names as delegates to
A.core.wikidata.
"""

from A.core.wikidata import (
    COMMON_PROPERTIES,
    get_common_properties,
    get_property_metadata as _get_property_metadata,
    search_languages as _search_languages,
    search_properties as _search_properties,
)


def semantika_search_languages(lingvo: str | None) -> list[str]:
    """Resolve language codes for Wikidata search.

    Delegates to ``A.core.wikidata.search_languages``.
    """
    return _search_languages(lingvo)


def wikidata_search_properties(
    query: str, languages: list[str]
) -> list[dict]:
    """Search Wikidata for properties matching a query.

    Delegates to ``A.core.wikidata.search_properties``.
    """
    return _search_properties(query, languages)


def wikidata_property_metadata(
    prop_id: str, languages: list[str]
) -> dict:
    """Fetch metadata for a single Wikidata property.

    Delegates to ``A.core.wikidata.get_property_metadata``.
    """
    return _get_property_metadata(prop_id, languages)
