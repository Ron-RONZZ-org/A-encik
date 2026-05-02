# AGENTS.md — Rules for A-encik

This file extends [A-workspace](./workspace/AGENTS.md).

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
└── data/
    └── storage.py     # SQLite + FTSConfig (uses A.data.search)
```

## EncikService Extension

EncikService extends CRUDService with:
- JSON serialization for complex columns
- **Core FTS5** full-text search (inherited from CRUDService)
- Title and UUID prefix lookups

**Note:** FTS5 implementation was migrated to A-core in 2025. EncikService now uses `CRUDService` FTS5 methods instead of duplicating logic.

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
## Branch Convention

All A-* repos use `main` as the primary branch. Use `main` for all development.
