"""Migration registration for A-encik.

This module registers the migration with A.core.migration framework.
Called via entry point "A.migrations" by A-core's unified migri command.
"""

from A.core.migration import register_migration, MigrationResult
from A_encik.data.migrate_from_autish import migrate as legacy_migrate


def _wrapper() -> MigrationResult:
    """Wrapper that converts old-style dict result to MigrationResult."""
    result = legacy_migrate()
    
    if isinstance(result, dict) and result.get("skipped"):
        return MigrationResult(
            module="A-encik",
            source_db="encik.db",
            target_table="encik",
            source_rows=0,
            migrated_rows=0,
            skipped=True,
            skipped_reason=result.get("reason", "unknown"),
        )
    
    return MigrationResult(
        module="A-encik",
        source_db="encik.db",
        target_table="encik",
        source_rows=result.get("source_rows", 0),
        migrated_rows=result.get("migrated_rows", 0),
        errors=result.get("errors", []),
    )


def register() -> None:
    """Register migration with A-core migration framework."""
    register_migration(
        module="A-encik",
        legacy_db="encik.db",
        target_table="encik",
        migrator=_wrapper,
    )


__all__ = ["register"]