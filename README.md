# A-encik

A-encik - personal knowledge management microapp

## Context

This module uses [A-workspace](https://github.com/Ron-RONZZ-org/A-workspace) as a **git submodule**:

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/Ron-RONZZ-org/A-encik.git
# Or if already cloned:
git submodule update --init --recursive
```

## Install

```bash
# Recommended — fast, reliable
pip install uv && uv pip install A-encik

# Traditional
pip install A-encik
```

Requires **A-core** (automatically installed as dependency).

## Usage

```bash
A encik ls            # List all knowledge entries
A encik vidi <uuid>  # View a knowledge entry
A encik serci <query>  # Full-text search (FTS5)
```

## Search

A-encik includes full-text search via SQLite FTS5:

- **Full-text search**: Matches titles, definitions, and content
- **French ligature support**: Search "cœur" finds "coeur" too
- **Fuzzy matching**: Typo tolerance (install `rapidfuzz` for speed)

```bash
# Full-text search
A encik serci "programming"

# Fuzzy search (requires: uv pip install rapidfuzz)
A encik serci "programmig" --fuzzy
```

## About

A-encik is a plugin for the [A](https://github.com/Ron-RONZZ-org/A-core/) framework.

**A-encik depends on A-core** for:
- Plugin discovery via entry points
- i18n (tr() for multilingual support)
- SQLite with WAL mode
- Shared utilities (error(), info(), run())

**A-encik optionally depends on A-vorto** for `ligilo` (link) relations between words and knowledge entries. If A-vorto is installed, bidirectional links are enabled.

See the [A-core documentation](https://github.com/Ron-RONZZ-org/A-core/) for more on the framework.

## Migration from autish

A-encik supports migration from autish:

```bash
A migri           # Run migrations (imports knowledge entries)
```

| Legacy | Target | Description |
|--------|--------|-------------|
| encik.db → encik | A-encik → encik | Knowledge (731 entries) |

## History

A-encik is based on [autish encik](https://github.com/Ron-RONZZ-org/autish/).

## License

GPL-3.0-only
---

**Branch:** Use `main` for all development.
