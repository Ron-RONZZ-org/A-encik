# AGENTS.md — Rules for A-encik

This file extends root A-core AGENTS.md for the A-encik plugin.

## Relationship to A-core

**A-encik depends on A-core** for:
- `A` package imports (i18n, output, subprocess, SQLite)
- Plugin discovery via entry points
- Shared utilities
- **API Reference**: See [A-core AGENTS.md](https://github.com/Ron-RONZZ-org/A-core/blob/main/AGENTS.md#api-reference)

**All source code must import from `A`, never duplicate utilities.**

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

## If You Need Something in Core

If you need a utility that should be in A-core:

1. **Search existing issues** on [A-core](https://github.com/Ron-RONZZ-org/A-core/issues)
2. **Create an issue** describing the need
3. **Wait for core enhancement** before implementing locally
4. **Use feature detection** when available

## Architecture

```
src/A_encik/
├── __init__.py       # Plugin exports
├── cli.py           # Typer app
├── service.py       # Business logic
│   └── semantika.py # Wikidata integration
└── data/
    └── storage.py  # SQLite (uses A.data.base)
```

## Code Standards

1. Use `tr()` for all user-facing strings
2. Use `error()` for errors, `info()` for info
3. Type hints on all public functions
4. Docstrings on all public functions
5. Tests required for all modules
6. Use WAL mode for SQLite

## What to Avoid

- Don't duplicate A-core utilities
- Don't skip i18n (use `tr()`)
- Don't use `print()` — use `A` output functions
- Don't hardcode paths — use `A.core.paths`
- Don't implement utilities that should be in core