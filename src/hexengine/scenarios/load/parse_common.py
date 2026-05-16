"""Shared helpers for scenario TOML parsing (no schema-specific tables)."""

from __future__ import annotations


def _optional_nonempty_str(raw: dict, key: str) -> str | None:
    """TOML value as stripped string, or None if missing / blank."""
    if key not in raw:
        return None
    v = raw[key]
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None
