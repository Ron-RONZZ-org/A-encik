"""ENC format parser and serializer for encik entries.

The .enc format is a TOML-based format for knowledge entries.
"""

from A_encik.enc_format._parser import parse_enc_file
from A_encik.enc_format._serializer import entry_to_enc

__all__ = ["parse_enc_file", "entry_to_enc", "validate_enc_entry"]


def validate_enc_entry(entry: dict) -> list[str]:
    """Validate an entry dict for required fields.

    Args:
        entry: Entry dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    terminologio = entry.get("terminologio") or {}
    difinoj = entry.get("difinoj") or {}

    if not terminologio:
        errors.append("Mankas terminologio")
    if not terminologio and not difinoj:
        errors.append("Mankas terminologio aŭ difinoj")

    # Validate UUID fields
    for field in ("superklaso",):
        values = entry.get(field, [])
        if isinstance(values, list):
            for v in values:
                if isinstance(v, str) and not _looks_like_uuid(v):
                    errors.append(f"Nevalida UUID en {field}: {v}")

    return errors


def _looks_like_uuid(s: str) -> bool:
    """Check if a string looks like a UUID (hex with optional hyphens).

    Handles ``#`` prefix (autish-legacy convention) by stripping it first.
    """
    import re
    cleaned = s.lstrip("#").replace("-", "")
    return bool(re.fullmatch(r"[0-9a-fA-F]{8,}", cleaned))
