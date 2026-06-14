"""pytest configuration for A-encik tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from A.core.testing import patch_paths


@pytest.fixture(autouse=True)
def isolate_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate all tests to a tmp_path database to prevent test data leakage.

    Redirects ``data_dir()`` via ``A_DIR`` env var and resets the DB
    singleton so the next ``get_db()`` call recomputes the path.
    """
    import A_encik.data.storage as storage_module

    patch_paths(monkeypatch, tmp_path)
    storage_module._db_instance = None
