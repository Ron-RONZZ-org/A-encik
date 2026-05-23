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
| `generi` | `generi` | ✓ delegates to A-agento (runtime detection) |
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
├── __init__.py              # exports: app
├── cli.py                  # Typer app (crud + semantika)
├── service.py              # EncikService (CRUD + FTS + reconciliation)
├── _display.py             # Output formatting (table, preview, link display)
├── _enc_processor.py       # Text processing (markup conversion, LaTeX fix, preview)
├── _search_mixin.py        # FTS5 + SQL search logic (~250 lines)
├── _reconcile_mixin.py     # Reconciliation logic (~356 lines)
├── _validation.py          # Input validation (required_fields, deduplicate, etc.)
├── data/
│   ├── __init__.py
│   ├── storage.py          # SQLite (get_db, schema, FTS config)
│   ├── _cache_db.py        # Semantic cache DB connection + schema
│   ├── _cache_lookup.py    # Property lookup (lookup_property)
│   ├── _cache_api.py       # API-based caching
│   ├── _cache_negative.py  # Negative cache (404s)
│   ├── _cache_store.py     # Property storage (store_property)
│   ├── _cache_maintenance.py # GC and maintenance
│   └── semantika_cache.py  # Semantic cache facade (~34 lines)
└── semantika/
    └── __init__.py         # Semantika CLI sub-app (grupo + serci)
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
| ``encik semantika grupo vidi <name>`` | Show semantic links in a group |
| ``encik semantika grupo ls`` | List all groups |
| ``encik semantika grupo aldoni <name>`` | Create a new empty group |
| ``encik semantika grupo modifi <old> <new>`` | Rename a group |
| ``encik semantika grupo forigi <name>`` | Delete a group |
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

1. Use `tr_multi()` for all user-facing strings (3-language inline: eo, en, fr)
2. Use `error()` for errors, `info()` for info
3. Type hints on all public functions
4. Docstrings on all public functions
5. Tests required for all modules
6. Use WAL mode for SQLite
7. FTS5 for full-text search



## Package Manager: `uv` is Required

All A-ecosystem development **must** use `uv` as the package manager:

| Operation | Command |
|-----------|---------|
| Install dependencies | `uv pip install <pkg>` |
| Install project in dev mode | `uv pip install -e .` |
| Run tests | `uv run pytest tests/` |
| Install CLI tools (poetry, etc.) | `uv tool install <tool>` |
| Add dev dependency | `uv add --dev <pkg>` |

**Exceptions:**
- `pip` in README install instructions is acceptable for end users who may not have `uv`
- Readthedocs platform build may require `pip` (platform constraint)
- Runtime `install-on-confirmation` code may fall back to `pip` if `uv` is unavailable (see A-core AGENTS.md)

## What to Avoid

- Don't duplicate A-core utilities
- Don't skip i18n (use `tr_multi()`)
- Don't use `print()` — use `A` output functions
- Don't hardcode paths — use `A.core.paths`
- Don't implement utilities that should be in core
- **generi** (previous TODO stub): now implemented — delegates to A-agento via runtime detection. If A-agento is not installed, prompts user to install it.
- **semantika**: already fully implemented (semantika-serci, semantika grupo subcommands)

## Database Schema Migrations

Schema changes (column additions, removals, renames) run on every `get_db()` 
call in `data/storage.py`. When removing a legacy column:

1. **Drop dependent indexes first** — SQLite refuses `DROP COLUMN` if 
   any index references the column. Check with:
   ```sql
   SELECT name FROM sqlite_master WHERE type='index' AND sql LIKE '%col_name%'
   ```
2. **Backfill data** from the old column to the new representation before dropping.
3. **Wrap in try/except with logging** — never use `except Exception: pass`.
4. **Set fallback in application code** so entry creation doesn't crash on old DBs
   that still have the `NOT NULL` constraint.

### Example: `titolo` removal

```python
# storage.py: drop dependent indexes + column
for _idx in ("idx_encik_titolo_lower", "idx_encik_titolo_fold"):
    db.execute(f"DROP INDEX IF EXISTS {_idx}")
db.execute("ALTER TABLE encik DROP COLUMN titolo")

# service.py: set fallback for backward compat
if "titolo" not in data:
    data["titolo"] = data.get("terminologio", {}).get("eo", "")
```

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
