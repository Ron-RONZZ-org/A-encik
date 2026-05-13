"""Semantic entry search — condition parsing and entry matching.

Port of autish-legacy ``semantika-serci`` condition system.
"""

from __future__ import annotations

import re
from typing import Any

from A_encik.semantika.config import normalize_semantika_ligilo

_SEMANTIKA_RANGE_RE = re.compile(r"^\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)$")
_SEMANTIKA_BOOL_TRUE: frozenset[str] = frozenset({"true", "vero", "jes", "j", "1"})
_SEMANTIKA_BOOL_FALSE: frozenset[str] = frozenset({"false", "malvero", "ne", "n", "0"})


def _compile_semantika_text_pattern(pattern: str, *, field: str) -> re.Pattern[str]:
    """Compile a text pattern with glob-style ``*`` wildcards into a regex."""
    if "\n" in pattern:
        raise ValueError(f"Nevalida {field}: tekst-kondiĉo ne povas enhavi novliniojn.")
    regex_src = "^" + re.escape(pattern).replace(r"\*", r"[^\n]*") + "$"
    return re.compile(regex_src, re.IGNORECASE)


def _parse_semantika_float(raw: object, *, field: str) -> float:
    """Parse a numeric value from a semantic condition.

    Accepts both ``,`` and ``.`` as decimal separator (matching autish-legacy
    behavior for Esperanto locale where comma is the standard decimal mark).
    """
    text = str(raw or "").strip().replace(",", ".")
    try:
        return float(text)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Nevalida {field}: ne povis interpreti nombron '{raw}'."
        ) from exc


def _parse_semantika_bool(raw: object, *, field: str) -> bool:
    """Parse a boolean value from a semantic condition."""
    lowered = str(raw or "").strip().lower()
    if lowered in _SEMANTIKA_BOOL_TRUE:
        return True
    if lowered in _SEMANTIKA_BOOL_FALSE:
        return False
    raise ValueError(f"Nevalida {field}: nevalida valoro '{raw}'.")


def _parse_semantika_str(raw: object) -> str:
    """Parse a string value from a semantic condition."""
    return str(raw or "").strip()


def parse_semantika_serci_conditions(raw_query: str) -> list[dict[str, Any]]:
    """Parse a semantika-serci query string into a list of conditions.

    Conditions are separated by ``;``.  Each condition has the form::

        ARKO valoro

    Where *valoro* can be:

    - A range ``(min,max)`` — numeric range check
    - A boolean ``true``/``false`` — boolean equality check
    - A text pattern with ``*`` wildcards — glob-style match

    Example::

        "wdt:P1082 (0,1000); wdt:P31 true; wdt:P5191 *philosophia*"

    Args:
        raw_query: The raw condition string.

    Returns:
        List of condition dicts with keys: kind, arko, (valoro|regex|minimumo|maksimumo).

    Raises:
        ValueError: On invalid syntax.
    """
    clauses = [part.strip() for part in str(raw_query or "").split(";") if part.strip()]
    if not clauses:
        raise ValueError(
            "Nevalida semantika-serci: mankas kondiĉoj. "
            "Ekzemplo: `wdt:P5191 *philosophia*; wdt:P1082 (0,1000)`."
        )

    conditions: list[dict[str, Any]] = []
    for idx, clause in enumerate(clauses, start=1):
        arc_token, sep, expression = clause.partition(" ")
        if not sep or not expression.strip():
            raise ValueError(
                f"Nevalida semantika-serci kondiĉo {idx}: "
                "uzu `ARKO valoro` (ekz. `wdt:P31 true`)."
            )
        arko = normalize_semantika_ligilo(arc_token.strip())
        if not arko:
            raise ValueError(f"Nevalida semantika-serci kondiĉo {idx}: arko mankas.")
        expression = expression.strip()
        range_match = _SEMANTIKA_RANGE_RE.fullmatch(expression)
        field_name = f"semantika-serci kondiĉo {idx}"

        if range_match:
            lower = _parse_semantika_float(range_match.group(1), field=field_name)
            upper = _parse_semantika_float(range_match.group(2), field=field_name)
            if lower > upper:
                raise ValueError(
                    f"Nevalida {field_name}: minimumo ne povas esti "
                    "pli granda ol maksimumo."
                )
            conditions.append({
                "kind": "range", "arko": arko,
                "minimumo": lower, "maksimumo": upper,
            })
            continue

        lowered = expression.lower()
        if lowered in _SEMANTIKA_BOOL_TRUE or lowered in _SEMANTIKA_BOOL_FALSE:
            conditions.append({
                "kind": "bool", "arko": arko,
                "valoro": _parse_semantika_bool(expression, field=field_name),
            })
            continue

        text_pattern = _parse_semantika_str(expression)
        conditions.append({
            "kind": "text", "arko": arko,
            "regex": _compile_semantika_text_pattern(text_pattern, field=field_name),
        })

    return conditions


def _matches_semantika_condition(
    semantikaj_valoroj: list[dict[str, Any]],
    condition: dict[str, Any],
) -> bool:
    """Check if a single semantic condition matches the entry's values."""
    kind = str(condition.get("kind") or "")
    arko = str(condition.get("arko") or "")
    if not kind or not arko:
        return False
    for item in semantikaj_valoroj:
        if str(item.get("arko") or "") != arko:
            continue
        tipo = str(item.get("tipo") or "")
        valoro = item.get("valoro")

        if kind == "text":
            if tipo != "str":
                continue
            regex = condition.get("regex")
            if isinstance(regex, re.Pattern) and regex.fullmatch(str(valoro or "")):
                return True
        elif kind == "bool":
            if tipo != "bool":
                continue
            expected = bool(condition.get("valoro"))
            if bool(valoro) == expected:
                return True
        elif kind == "range":
            if tipo not in {"int", "float"}:
                continue
            current = _parse_semantika_float(valoro, field="semantika-serci")
            minimumo = float(condition.get("minimumo") or 0.0)
            maksimumo = float(condition.get("maksimumo") or 0.0)
            if minimumo <= current <= maksimumo:
                return True
    return False


def _normalize_semantika_valoroj(
    raw_value: object,
) -> list[dict[str, Any]]:
    """Normalise the ``semantika`` field of an entry into a list of value dicts."""
    if isinstance(raw_value, list):
        return [item for item in raw_value if isinstance(item, dict)]
    if isinstance(raw_value, str):
        try:
            import json
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def entry_matches_semantika_conditions(
    entry: dict[str, Any],
    conditions: list[dict[str, Any]],
) -> bool:
    """Check if an entry matches all semantic conditions (AND logic).

    Args:
        entry: An encik entry dict.
        conditions: Parsed conditions from :func:`parse_semantika_serci_conditions`.

    Returns:
        True if the entry matches all conditions.
    """
    semantikaj_valoroj = _normalize_semantika_valoroj(entry.get("semantika"))
    if not semantikaj_valoroj:
        return False
    return all(
        _matches_semantika_condition(semantikaj_valoroj, condition)
        for condition in conditions
    )
