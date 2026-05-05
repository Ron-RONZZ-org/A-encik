"""JSON serialization utilities for SQLite."""

from __future__ import annotations

import json
from typing import Any


def serialize_json_columns(
    data: dict[str, Any],
    columns: tuple[str, ...],
) -> dict[str, Any]:
    """Serialize specified list/dict columns to JSON strings for SQLite.

    Args:
        data: Dictionary with column values
        columns: Column names to serialize (only if they contain list/dict)

    Returns:
        New dict with specified columns converted to JSON strings

    Example:
        >>> data = {"teksto": "hello", "difinoj": ["def1", "def2"]}
        >>> serialize_json_columns(data, ("difinoj",))
        {"teksto": "hello", "difinoj": '["def1", "def2"]'}
    """
    result = dict(data)
    for col in columns:
        if col in result and isinstance(result[col], (list, dict)):
            result[col] = json.dumps(result[col], ensure_ascii=False)
    return result


def deserialize_json_columns(
    data: dict[str, Any],
    columns: tuple[str, ...],
) -> dict[str, Any]:
    """Deserialize specified JSON string columns from SQLite.

    Args:
        data: Dictionary with column values
        columns: Column names to deserialize

    Returns:
        New dict with specified columns converted to list/dict

    Example:
        >>> data = {"teksto": "hello", "difinoj": '["def1", "def2"]'}
        >>> deserialize_json_columns(data, ("difinoj",))
        {"teksto": "hello", "difinoj": ["def1", "def2"]}
    """
    result = dict(data)
    for col in columns:
        if col in result and isinstance(result[col], str):
            try:
                result[col] = json.loads(result[col])
            except (json.JSONDecodeError, TypeError):
                pass  # Keep original value if not valid JSON
    return result


__all__ = ["serialize_json_columns", "deserialize_json_columns"]