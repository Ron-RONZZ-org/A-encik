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
pip install A-encik
```

Requires **A-core** (automatically installed as dependency).

## Usage

```bash
A encik ls            # List all knowledge entries
A encik vidi <uuid>  # View a knowledge entry
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

## History

A-encik is based on [autish encik](https://github.com/Ron-RONZZ-org/autish/).

## License

GPL-3.0-only