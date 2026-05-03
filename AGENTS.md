# AGENTS.md — Rules for A-encik

This file extends [A-workspace](./workspace/AGENTS.md).

## User Experience Consistency with autish-legacy

**CRITICAL**: A-encik must maintain feature parity and command compatibility with autish-legacy (`autish/commands/encik.py`) for user experience continuity.

### Command Compatibility Rule

Before adding new CLI commands or changing existing ones:
1. **Check autish-legacy** for the equivalent command
2. **Match the command signature exactly** - same args, same options
3. **Only add A-specific features** when autish-legacy doesn't have them

### Command Mapping (autish-legacy → A)

| autish-legacy | A-encik | Status |
|--------------|---------|--------|
| `agordi` | `agordi` | ✓ exact match required |
| `aldoni` | `aldoni` | ✓ exact match required |
| `modifi` | `modifi` | ✓ exact match required |
| `vidi` | `vidi` | ✓ exact match required |
| `eksporti` | `eksporti` | ✓ exact match required |
| `generi` | `generi` | ✓ exact match required |
| `semantika-serci` | `semantika-serci` | ✓ exact match required |
| `serci` | `serci` | ✓ exact match required |
| `ls` | `ls` | ✓ exact match required |
| `forigi` | `forigi` | ✓ exact match required |
| (none) | `grafo` | A-only bonus |
| (none) | `repacigi` | A-only bonus |

### Output Format

- Match autish-legacy console output format exactly
- Use same Rich styling conventions
- Match table columns and widths

### Data Paths

- autish-legacy: `~/.local/share/autish/encik.db`
- A: `~/.local/share/A/encik.db`

Migration must handle path changes transparently.

## Module-Specific Additions

### Relationship to A-core

**A-encik depends on A-core** for:
- `A` package imports (i18n, output, subprocess, SQLite)
- Plugin discovery via entry points
- Shared utilities
- **API Reference**: See [A-core AGENTS.md](./A-core/AGENTS.md#api-reference)

**All source code must import from `A`, never duplicate utilities.**

## Relationship to autish-legacy

**A-encik is a rewrite of autish encik** — replicate full functionality.

- Schema: See `autish-legacy/autish/services/encik_repo.py`
- Commands: See `autish-legacy/autish/commands/encik.py`
- When in doubt, consult autish-legacy source

## Optional Dependency on A-vorto

In autish, encik and vorto share `ligilo` (link) relations. In A:

- **A-encik optionally depends on A-vorto:**
  ```python
  def create_ligilo(to_uuid: str) -> None:
      """Create bi-directional link to word entry."""
      try:
          import A_vorto
          A_vorto.add_link(to_uuid)
      except ImportError:
          # A-vorto not installed - feature unavailable
          pass
  ```

- **Detect at call time, not import time**
- **Gracefully degrade** if A-vorto is not installed
- **Never require** A-vorto as hard dependency

## Architecture

```
src/A_encik/
├── __init__.py           # Plugin exports
├── cli.py              # Typer app
├── service.py          # EncikService (extends CRUDService + core FTS5)
├── semantika/          # Semantic link management
│   ├── __init__.py     # Exports
│   ├── config.py       # CSV group loading/writing, default definitions
│   ├── wikidata.py     # Wikidata API client (search + metadata)
│   └── search.py       # Condition parsing + entry matching
└── data/
    └── storage.py     # SQLite + FTSConfig (uses A.data.search)
```

## EncikService Extension

EncikService extends CRUDService with:
- JSON serialization for complex columns
- **Core FTS5** full-text search (inherited from CRUDService)
- Title and UUID prefix lookups
- Semantic entry search via ``search_semantika()``

**Note:** FTS5 implementation was migrated to A-core in 2025. EncikService now uses `CRUDService` FTS5 methods instead of duplicating logic.

## Semantika (Semantic Link Management)

Three-layer system for structured knowledge:

| Layer | Component | Description |
|-------|-----------|-------------|
| Catalog | ``semantika/config.py`` | CSV-based group files in ``~/.config/A/encik/semantika/*.csv`` defining semantic relationship types (23 built-in, extendable) |
| Discovery | ``semantika/wikidata.py`` | Wikidata ``wbsearchentities``/``wbgetentities`` for property search and metadata lookup |
| Search | ``semantika/search.py`` | Parse conditions (range, bool, text with ``*``) and match against entries' ``semantika`` JSON field — AND logic |

### CLI Commands

| Command | What it does |
|---------|-------------|
| ``encik semantika <group>`` | Show semantic links in a category (dynamically registered per CSV) |
| ``encik semantika serci <query>`` | Search Wikidata + local CSVs for property definitions |
| ``encik semantika aldoni <id> <group>`` | Add a Wikidata property to a CSV group with validation |
| ``encik semantika-serci <conditions>`` | Filter entries by semantic conditions |

### JSON Fields

| Type | Fields |
|------|--------|
| List | `superklaso`, `ligilo`, `fonto`, `citajo`, `semantika` |
| Dict | `terminologio`, `difinoj`, `datumo` |

### EncikService Methods

```python
from A_encik.service import get_service

service = get_service()
service.create({"titolo": "...", "terminologio": {"eo": "..."}})
service.get(uuid)
service.list()
service.search_fts(query)
service.find_by_titolo(titolo)
service.find_by_uuid_prefix(prefix)
service.update(uuid, {"titolo": "..."})
service.delete(uuid, soft=True)
```

## Code Standards

1. Use `tr()` for all user-facing strings
2. Use `error()` for errors, `info()` for info
3. Type hints on all public functions
4. Docstrings on all public functions
5. Tests required for all modules
6. Use WAL mode for SQLite
7. FTS5 for full-text search

## What to Avoid

- Don't duplicate A-core utilities
- Don't skip i18n (use `tr()`)
- Don't use `print()` — use `A` output functions
- Don't hardcode paths — use `A.core.paths`
- Don't implement utilities that should be in core
- **generi/semantika**: requires A-AI rewrite — implement as TODO stubs

## Migration from autish

A-encik supports migration from autish encik.db:

| Legacy | Target | Description |
|--------|--------|-------------|
| encik.db → encik | A-encik → encik | Knowledge (731 entries) |

**CLI:**
```bash
A migri           # Run migrations
```

**Programmatic:**
```python
from A_encik.data.migrate_from_autish import migrate
result = migrate()
```

Features:
- JSON field conversions (terminologio, difinoj, superklaso, ligilo, fonto, citajo, datumo, semantika)
- Preserves UUIDs and timestamps
- Idempotent

## Branch Convention
All A-* repos use `main` as the primary branch. Use `main` for all development.
