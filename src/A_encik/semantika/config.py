"""Semantic link catalog — CSV-based group management.

Port of autish-legacy semantika config system.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from A.core.paths import config_dir

# ──────────────────────────────────────────────────────────────────────────────
# Default semantic link definitions
# ──────────────────────────────────────────────────────────────────────────────

# (canonical, description, (aliases, ...))
SEMANTIKA_LIGILO_DEFINOJ: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("rdf:type", "estas tipo de (klasigo)", ("rdf:type", "type", "estas tipo de", "wdt:p31", "p31", "instance of", "instanco de")),
    ("rdf:hasInstance", "havas instancon (inversa de rdf:type)", ("rdf:hasinstance",)),
    ("rdfs:subClassOf", "subklaso de", ("rdfs:subclassof", "subklaso de", "wdt:p279", "p279", "subclass of")),
    ("rdfs:hasSubClass", "havas subklason (inversa de rdfs:subClassOf)", ("rdfs:superclassof", "superklaso de")),
    ("owl:disjointWith", "malkongrua kun", ("owl:disjointwith", "malkongrua kun")),
    ("owl:inverseOf", "inversa de", ("owl:inverseof", "inversa de")),
    ("wdt:P50", "aŭtoro / kreinto", ("p50", "author", "creator", "aŭtoro", "kreinto")),
    ("wdt:P361", "parto de", ("p361", "part of", "parto de")),
    ("wdt:P527", "havas parton", ("p527", "has part", "havas parton")),
    ("wdt:P276", "loko / situas en", ("p276", "located in", "location", "loko")),
    ("wdt:P463", "membro de", ("p463", "member of", "membro de")),
    ("wdt:P106", "okupo / profesio", ("p106", "occupation", "profession", "okupo", "profesio")),
    ("wdt:P26", "geedzo / partnero", ("p26", "spouse", "partner", "geedzo")),
    ("wdt:P123", "eldonisto / publikigita de", ("p123", "publisher", "published by", "eldonisto")),
    ("wdt:P69", "edukita ĉe", ("p69", "educated at", "edukita ĉe")),
    ("wdt:P569", "dato de naskiĝo", ("p569", "date of birth", "naskigxdato", "naskiĝo")),
    ("wdt:P570", "dato de morto", ("p570", "date of death", "morto")),
    ("wdt:P17", "lando", ("p17", "country", "lando")),
    ("wdt:P131", "situas en administra unuo", ("p131", "located in admin unit")),
    ("wdt:P571", "fondita / komenco", ("p571", "inception", "fondita")),
    ("wdt:P5191", "devenas de leksiko", ("p5191", "derived from lexeme", "etimologio", "devenas de")),
    ("wdt:P2046", "areo (geografia kvanto)", ("p2046", "area", "surface area", "areo")),
    ("wdt:P1082", "loĝantaro / populacio", ("p1082", "population", "loĝantaro", "populacio")),
)

# Default groups with canonical link lists
SEMANTIKA_KATEGORIOJ: dict[str, tuple[str, ...]] = {
    "generala": ("rdf:type", "rdf:hasInstance", "rdfs:subClassOf", "rdfs:hasSubClass", "owl:disjointWith", "owl:inverseOf", "wdt:P361", "wdt:P527"),
    "persono": ("rdf:type", "rdfs:subClassOf", "wdt:P50", "wdt:P106", "wdt:P69", "wdt:P26", "wdt:P463", "wdt:P569", "wdt:P570"),
    "geografio": ("rdf:type", "rdfs:subClassOf", "wdt:P17", "wdt:P131", "wdt:P276", "wdt:P361", "wdt:P527", "wdt:P2046", "wdt:P1082"),
    "abstrakta": ("rdf:type", "rdfs:subClassOf", "owl:disjointWith", "owl:inverseOf", "wdt:P5191", "wdt:P571", "wdt:P123"),
}

SEMANTIKA_HELPO_TEKSTO = (
    "Semantic link types for Encik knowledge graph.\n"
    "Organized by group in ~/.config/A/encik/semantika/*.csv "
    "(LIGILO, PRISKRIBO, ALIAZOJ columns).\n"
    "\n"
    "Subcommands:\n"
    "- encik semantika serci <query>        Search Wikidata + local groups\n"
    "- encik semantika aldoni <id> <group>  Add semantic link to group\n"
    "- encik semantika forigi <id> <group>  Delete semantic link from group\n"
    "- encik semantika modifi <id> <group>  Modify a semantic link\n"
    "- encik semantika grupo ls             List all groups\n"
    "- encik semantika grupo vidi <name>    Show entries in a group\n"
    "- encik semantika grupo aldoni <name>  Create a new group\n"
    "- encik semantika grupo modifi <old> <new>  Rename a group\n"
    "- encik semantika grupo forigi <name>  Delete a group"
)

# Derived lookup maps
_SEMANTIKA_LIGILO_MAP: dict[str, str] = {}
for canonical, _, aliases in SEMANTIKA_LIGILO_DEFINOJ:
    _SEMANTIKA_LIGILO_MAP[canonical.lower()] = canonical
    for alias in aliases:
        _SEMANTIKA_LIGILO_MAP[alias.lower()] = canonical

_KANONAJ_SEMANTIKAJ_LIGILOJ: set[str] = {c for c, _, _ in SEMANTIKA_LIGILO_DEFINOJ}

_SEMANTIKA_DEFINOJ_MAP: dict[str, tuple[str, tuple[str, ...]]] = {
    c: (d, a) for c, d, a in SEMANTIKA_LIGILO_DEFINOJ
}

# Config directory
_SEMANTIKA_CONFIG_DIR: Path | None = None
_SEMANTIKA_CONFIG_CACHE: dict[str, Any] = {"signature": None, "groups": None}
_RESERVED_SUBCOMMANDS: frozenset[str] = frozenset(
    {"ls", "serci", "aldoni", "modifi", "forigi", "grupo"}
)
_CSV_HEADERS: tuple[str, str, str] = ("LIGILO", "PRISKRIBO", "ALIAZOJ")


def _get_config_dir() -> Path:
    """Get the semantika config directory."""
    global _SEMANTIKA_CONFIG_DIR
    if _SEMANTIKA_CONFIG_DIR is None:
        _SEMANTIKA_CONFIG_DIR = config_dir() / "encik" / "semantika"
    return _SEMANTIKA_CONFIG_DIR


# ──────────────────────────────────────────────────────────────────────────────
# Normalisation helpers
# ──────────────────────────────────────────────────────────────────────────────


def normalize_semantika_ligilo(raw: str | None) -> str | None:
    """Normalise a semantic link string via alias map."""
    if not raw:
        return None
    value = str(raw).strip()
    if not value:
        return None
    return _SEMANTIKA_LIGILO_MAP.get(value.lower(), value)


def normalize_semantika_group_name(raw: str) -> str:
    """Normalise a group name to a valid filename stem."""
    normalized = str(raw or "").strip().lower().replace(" ", "-")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", normalized):
        raise ValueError("Nevalida grupo: uzu nur minusklojn, ciferojn, '-' aŭ '_'.")
    return normalized


def normalize_semantika_add_id(raw_id: str) -> tuple[str, str | None]:
    """Parse a semantic link ID, returning (ligilo, prop_id).

    ``"P1234"`` → ``("wdt:P1234", "P1234")``
    ``"wdt:P1234"`` → ``("wdt:P1234", "P1234")``
    ``"rdf:type"`` → ``("rdf:type", None)``
    """
    token = str(raw_id or "").strip()
    if not token:
        raise ValueError("Mankas semantika ID.")
    prop_match = re.fullmatch(r"[Pp](\d+)", token)
    if prop_match:
        prop_id = f"P{prop_match.group(1)}"
        return f"wdt:{prop_id}", prop_id
    wdt_match = re.fullmatch(r"wdt:[Pp](\d+)", token, flags=re.IGNORECASE)
    if wdt_match:
        prop_id = f"P{wdt_match.group(1)}"
        return f"wdt:{prop_id}", prop_id
    normalized = normalize_semantika_ligilo(token) or token
    return normalized, None


def runtime_known_semantika_ligiloj() -> set[str]:
    """Return the set of all known semantic link IDs (built-in + CSV)."""
    result: set[str] = set(_KANONAJ_SEMANTIKAJ_LIGILOJ)
    for rows in load_semantika_groups().values():
        for row in rows:
            ligilo = str(row.get("ligilo") or "").strip()
            if ligilo:
                result.add(ligilo)
    return result


def _parse_alias_list(raw: str) -> list[str]:
    """Parse comma-separated alias string into list."""
    return [token.strip() for token in str(raw or "").split(",") if token.strip()]


# ──────────────────────────────────────────────────────────────────────────────
# CSV I/O
# ──────────────────────────────────────────────────────────────────────────────


def semantika_group_file(group_name: str) -> Path:
    """Return the CSV file path for a group."""
    return _get_config_dir() / f"{group_name}.csv"


def _default_semantika_group_rows() -> dict[str, list[tuple[str, str, str]]]:
    """Build default row triples from built-in categories."""
    rows_by_group: dict[str, list[tuple[str, str, str]]] = {}
    for group_name, canonicals in SEMANTIKA_KATEGORIOJ.items():
        rows: list[tuple[str, str, str]] = []
        for canonical in canonicals:
            description, aliases = _SEMANTIKA_DEFINOJ_MAP.get(canonical, ("", ()))
            alias_text = ",".join(dict.fromkeys(aliases))
            rows.append((canonical, description, alias_text))
        rows_by_group[group_name] = rows
    return rows_by_group


def write_semantika_group_rows(
    group_name: str,
    rows: list[dict[str, Any]],
) -> None:
    """Write semantic link rows to a group CSV file."""
    cfg_dir = _get_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    target = semantika_group_file(group_name)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_CSV_HEADERS)
        for row in rows:
            ligilo = str(row.get("ligilo") or "").strip()
            priskribo = str(row.get("priskribo") or "").strip()
            aliases = row.get("aliasoj")
            if isinstance(aliases, list):
                alias_text = ",".join(str(a).strip() for a in aliases if str(a).strip())
            else:
                alias_text = str(aliases or "").strip()
            if ligilo:
                writer.writerow([ligilo, priskribo, alias_text])


def _read_semantika_group_rows(path: Path) -> list[dict[str, Any]]:
    """Read rows from a single group CSV file."""
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not isinstance(row, dict):
                continue
            ligilo = str(row.get("LIGILO") or "").strip()
            if not ligilo:
                continue
            priskribo = str(row.get("PRISKRIBO") or "").strip()
            raw_aliases = str(row.get("ALIAZOJ") or "").strip()
            alias_list = _parse_alias_list(raw_aliases) if raw_aliases else []
            rows.append({"ligilo": ligilo, "priskribo": priskribo, "aliasoj": alias_list})
    return rows


def _config_signature() -> tuple[tuple[str, int], ...]:
    """Return a signature tuple (filename, mtime) for cache invalidation."""
    cfg_dir = _get_config_dir()
    if not cfg_dir.exists():
        return ()
    sig: list[tuple[str, int]] = []
    for path in sorted(cfg_dir.iterdir()):
        if path.suffix == ".csv" and path.exists():
            sig.append((path.name, int(path.stat().st_mtime)))
    return tuple(sig)


def ensure_semantika_group_files() -> None:
    """Create default group CSV files if they don't exist."""
    cfg_dir = _get_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    default_rows = _default_semantika_group_rows()
    for group_name, rows in default_rows.items():
        path = semantika_group_file(group_name)
        if not path.exists():
            write_semantika_group_rows(group_name, [
                {"ligilo": r[0], "priskribo": r[1], "aliasoj": _parse_alias_list(r[2])}
                for r in rows
            ])


def load_semantika_groups() -> dict[str, list[dict[str, Any]]]:
    """Load all semantic link groups (built-in defaults + CSV overrides)."""
    signature = _config_signature()
    cache = _SEMANTIKA_CONFIG_CACHE
    if cache["signature"] == signature and cache["groups"] is not None:
        return cache["groups"]

    ensure_semantika_group_files()
    groups: dict[str, list[dict[str, Any]]] = {}
    cfg_dir = _get_config_dir()
    if cfg_dir.exists():
        for path in sorted(cfg_dir.glob("*.csv")):
            group_name = path.stem.strip().lower()
            if group_name:
                groups[group_name] = _read_semantika_group_rows(path)

    cache["signature"] = signature
    cache["groups"] = groups
    return groups


def invalidate_config_cache() -> None:
    """Invalidate the cached groups (call after writing)."""
    global _SEMANTIKA_CONFIG_CACHE
    _SEMANTIKA_CONFIG_CACHE = {"signature": None, "groups": None}


def create_semantika_group(name: str) -> Path:
    """Create a new empty semantika group CSV file.

    Args:
        name: Group name (normalized via :func:`normalize_semantika_group_name`).

    Returns:
        Path to the created CSV file.

    Raises:
        ValueError: If name is invalid.
        FileExistsError: If group already exists.
    """
    group_name = normalize_semantika_group_name(name)
    path = semantika_group_file(group_name)
    if path.exists():
        raise FileExistsError(
            f"Group '{group_name}' already exists."
        )
    _get_config_dir().mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_CSV_HEADERS)
    invalidate_config_cache()
    return path


def rename_semantika_group(old_name: str, new_name: str) -> Path:
    """Rename a semantika group by renaming its CSV file.

    Args:
        old_name: Current group name.
        new_name: New group name.

    Returns:
        Path to the renamed CSV file.

    Raises:
        ValueError: If either name is invalid.
        FileNotFoundError: If old group does not exist.
        FileExistsError: If new group name already exists.
    """
    old = normalize_semantika_group_name(old_name)
    new = normalize_semantika_group_name(new_name)
    old_path = semantika_group_file(old)
    new_path = semantika_group_file(new)
    if not old_path.exists():
        raise FileNotFoundError(
            f"Group '{old}' does not exist."
        )
    if new_path.exists():
        raise FileExistsError(
            f"Group '{new}' already exists."
        )
    old_path.rename(new_path)
    invalidate_config_cache()
    return new_path


def delete_semantika_group(name: str) -> None:
    """Delete a semantika group CSV file.

    Args:
        name: Group name.

    Raises:
        ValueError: If name is invalid.
        FileNotFoundError: If group does not exist.
    """
    group_name = normalize_semantika_group_name(name)
    path = semantika_group_file(group_name)
    if not path.exists():
        raise FileNotFoundError(
            f"Group '{group_name}' does not exist."
        )
    path.unlink()
    invalidate_config_cache()
