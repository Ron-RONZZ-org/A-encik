"""Wikidata API client for semantic link discovery.

Port of autish-legacy Wikidata integration.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_WIKIDATA_USER_AGENT = "A-encik/0.1.0 (Wikidata semantika integration)"


def _semantika_language_priority(languages: list[str]) -> list[str]:
    """Ensure 'eo' and 'en' are included as fallbacks."""
    result = list(dict.fromkeys(languages))
    for fallback in ("eo", "en"):
        if fallback not in result:
            result.append(fallback)
    return result


def semantika_search_languages(lingvo: str | None) -> list[str]:
    """Resolve language codes for Wikidata search.

    Args:
        lingvo: User-supplied language code(s) or ``None``.

    Returns:
        Prioritised list of language codes.
    """
    if lingvo:
        parsed = [code.strip() for code in lingvo.split(",") if re.fullmatch(r"[a-z]{2}", code.strip().lower())]
        if not parsed:
            raise ValueError("Nevalida --lingvo. Uzu 2-litera(j)n kodojn (ekz: eo,en).")
        return _semantika_language_priority(parsed)
    env_lang = (os.environ.get("LC_ALL") or os.environ.get("LANG") or "").split(".")[0]
    env_code = env_lang.split("_")[0].strip().lower()
    if re.fullmatch(r"[a-z]{2}", env_code):
        return _semantika_language_priority([env_code])
    return ["eo", "en"]


def _wikidata_api_get(params: dict[str, str], *, timeout: float = 5.0) -> dict[str, Any]:
    """Make a GET request to the Wikidata API.

    Args:
        params: Query parameters.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: On network errors or invalid responses.
    """
    query = urllib.parse.urlencode(params)
    url = f"https://www.wikidata.org/w/api.php?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": _WIKIDATA_USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read().decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Wikidata API neatingebla") from exc
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Wikidata API respondo nevalida") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Wikidata API respondo nevalida")
    return data


def _extract_wikidata_entity_metadata(
    entity: dict[str, Any], *, prop_id: str, lang_list: list[str]
) -> dict[str, Any]:
    """Extract label, description, and aliases from a Wikidata entity dict."""
    labels = entity.get("labels")
    descriptions = entity.get("descriptions")
    aliases_obj = entity.get("aliases")
    label = ""
    description = ""
    if isinstance(labels, dict):
        for lang in lang_list:
            payload = labels.get(lang)
            if isinstance(payload, dict) and str(payload.get("value") or "").strip():
                label = str(payload.get("value") or "").strip()
                break
    if isinstance(descriptions, dict):
        for lang in lang_list:
            payload = descriptions.get(lang)
            if isinstance(payload, dict) and str(payload.get("value") or "").strip():
                description = str(payload.get("value") or "").strip()
                break
    alias_values: list[str] = []
    if isinstance(aliases_obj, dict):
        for lang in lang_list:
            payload = aliases_obj.get(lang)
            if not isinstance(payload, list):
                continue
            for alias_entry in payload:
                if not isinstance(alias_entry, dict):
                    continue
                value = str(alias_entry.get("value") or "").strip()
                if value and value.lower() not in {a.lower() for a in alias_values}:
                    alias_values.append(value)
    if prop_id.lower() not in {alias.lower() for alias in alias_values}:
        alias_values.append(prop_id.lower())
    return {"etikedo": label, "priskribo": description, "aliasoj": alias_values}


def wikidata_search_properties(
    query: str, languages: list[str]
) -> list[dict[str, Any]]:
    """Search Wikidata for properties matching a query.

    Args:
        query: Free-text search string.
        languages: Prioritised language codes.

    Returns:
        List of result dicts with keys: ligilo, priskribo, aliasoj, etikedo, fonto.
    """
    dedup: dict[str, dict[str, Any]] = {}
    for lang in languages:
        data = _wikidata_api_get({
            "action": "wbsearchentities",
            "format": "json",
            "language": lang,
            "uselang": lang,
            "type": "property",
            "limit": "15",
            "search": query,
        })
        results = data.get("search")
        if not isinstance(results, list):
            continue
        for item in results:
            if not isinstance(item, dict):
                continue
            prop_id = str(item.get("id") or "").strip()
            if not re.fullmatch(r"P\d+", prop_id):
                continue
            ligilo = f"wdt:{prop_id}"
            label = str(item.get("label") or "").strip()
            description = str(item.get("description") or "").strip()
            aliases: list[str] = []
            match_obj = item.get("match")
            if isinstance(match_obj, dict):
                text = str(match_obj.get("text") or "").strip()
                if text and text.lower() != label.lower():
                    aliases.append(text)
            if prop_id.lower() not in {alias.lower() for alias in aliases}:
                aliases.append(prop_id.lower())
            existing = dedup.get(ligilo)
            if existing is None:
                dedup[ligilo] = {
                    "ligilo": ligilo,
                    "priskribo": description,
                    "aliasoj": aliases,
                    "etikedo": label,
                    "fonto": "wikidata",
                }
            else:
                if not str(existing.get("priskribo") or "") and description:
                    existing["priskribo"] = description
                combined = [str(a) for a in existing.get("aliasoj") or []]
                for alias in aliases:
                    if alias.lower() not in {a.lower() for a in combined}:
                        combined.append(alias)
                existing["aliasoj"] = combined

    # Enrich with property metadata
    if dedup:
        prop_ids = [ligilo.split(":", 1)[1] for ligilo in dedup]
        try:
            metadata = _wikidata_properties_metadata(prop_ids, languages)
        except RuntimeError:
            metadata = {}
        for ligilo, item in dedup.items():
            prop_id = ligilo.split(":", 1)[1]
            localized = metadata.get(prop_id)
            if not localized:
                continue
            localized_label = str(localized.get("etikedo") or "").strip()
            localized_desc = str(localized.get("priskribo") or "").strip()
            if localized_label:
                item["etikedo"] = localized_label
            if localized_desc:
                item["priskribo"] = localized_desc
            merged: list[str] = []
            for alias in [
                *[str(a) for a in (localized.get("aliasoj") or [])],
                *[str(a) for a in (item.get("aliasoj") or [])],
            ]:
                cleaned = alias.strip()
                if cleaned and cleaned.lower() not in {a.lower() for a in merged}:
                    merged.append(cleaned)
            if merged:
                item["aliasoj"] = merged

    return list(dedup.values())


def _wikidata_properties_metadata(
    prop_ids: list[str], languages: list[str]
) -> dict[str, dict[str, Any]]:
    """Fetch metadata for multiple Wikidata properties."""
    normalized: list[str] = []
    for raw_id in prop_ids:
        candidate = str(raw_id or "").strip().upper()
        if re.fullmatch(r"P\d+", candidate) and candidate not in normalized:
            normalized.append(candidate)
    if not normalized:
        return {}
    lang_list = _semantika_language_priority(languages)
    data = _wikidata_api_get({
        "action": "wbgetentities",
        "format": "json",
        "ids": "|".join(normalized),
        "props": "labels|descriptions|aliases",
        "languages": "|".join(lang_list),
    })
    entities = data.get("entities")
    if not isinstance(entities, dict):
        raise RuntimeError("Wikidata API respondo ne enhavas 'entities'")
    extracted: dict[str, dict[str, Any]] = {}
    for prop_id in normalized:
        entity = entities.get(prop_id)
        if isinstance(entity, dict):
            extracted[prop_id] = _extract_wikidata_entity_metadata(
                entity, prop_id=prop_id, lang_list=lang_list,
            )
    return extracted


def wikidata_property_metadata(
    prop_id: str, languages: list[str]
) -> dict[str, Any]:
    """Fetch metadata for a single Wikidata property.

    Args:
        prop_id: e.g. ``"P1082"``
        languages: Prioritised language codes.

    Returns:
        Dict with keys: etikedo, priskribo, aliasoj.
    """
    lang_list = _semantika_language_priority(languages)
    data = _wikidata_api_get({
        "action": "wbgetentities",
        "format": "json",
        "ids": prop_id,
        "props": "labels|descriptions|aliases",
        "languages": "|".join(lang_list),
    })
    entities = data.get("entities")
    if not isinstance(entities, dict):
        raise RuntimeError("Wikidata API respondo ne enhavas 'entities'")
    entity = entities.get(prop_id)
    if not isinstance(entity, dict):
        raise RuntimeError("Wikidata API respondo ne enhavas la petitan ID")
    return _extract_wikidata_entity_metadata(
        entity, prop_id=prop_id, lang_list=lang_list,
    )
