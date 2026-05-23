"""Wikidata API query with circuit breaker for semantika cache."""

from __future__ import annotations

import time

from A import warning as _warn


# Last API failure timestamp for circuit breaker
_last_api_failure: float = 0.0
_CIRCUIT_BREAKER_SECONDS = 60


def _query_wikidata_api(keyword: str, retries: int = 2) -> list[dict] | None:
    """Query Wikidata API for properties matching keyword.

    Always queries with English priority. Retries on failure.
    Includes circuit breaker for repeated failures.

    Args:
        keyword: English keyword
        retries: Number of retry attempts (default 2)

    Returns:
        List of property dicts or None
    """
    global _last_api_failure

    # Circuit breaker: warn if active but still try the API
    if time.time() - _last_api_failure < _CIRCUIT_BREAKER_SECONDS:
        _warn("Wikidata API circuit breaker active — retrying anyway")

    for attempt in range(1, retries + 2):  # initial + retries
        try:
            from A.core.wikidata import search_properties
            results = search_properties(keyword, languages=["en", "eo", "fr"])
            if results:
                # Deduplicate by id before returning
                seen_ids: set[str] = set()
                deduped = []
                for r in results:
                    from A_encik.data._cache_lookup import _extract_property_id
                    rid = _extract_property_id(r.get("ligilo", ""))
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        deduped.append({
                            "id": rid,
                            "label": r.get("etikedo", ""),
                            "description": r.get("priskribo", ""),
                            "label_eo": "",
                        })
                if deduped:
                    _last_api_failure = 0.0  # reset circuit breaker on success
                    return deduped
                return None  # API succeeded but no results
            # No results: store negative cache tombstone
            from A_encik.data._cache_negative import _store_negative_cache
            _store_negative_cache(keyword)
            return None
        except ImportError:
            return None
        except RuntimeError as e:
            # Extract detail from chained exception for actionable messages
            cause = e.__cause__
            detail = str(cause) if cause else str(e)
            if attempt <= retries:
                _warn(f"Wikidata API retry {attempt}/{retries} for '{keyword}': {detail}")
                time.sleep(2.0)
            else:
                _warn(f"Wikidata API query failed for '{keyword}': {detail}")
                _last_api_failure = time.time()
                return None
        except Exception as e:
            if attempt <= retries:
                _warn(f"Wikidata API retry {attempt}/{retries} for '{keyword}': {e}")
                time.sleep(2.0)
            else:
                _warn(f"Wikidata API query failed for '{keyword}': {e}")
                _last_api_failure = time.time()
                return None
    return None
