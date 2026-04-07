"""
Installed `hexes` package version string for server/client comparison.
"""

from __future__ import annotations

import re


def hexes_package_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("hexes")
    except (PackageNotFoundError, Exception):
        try:
            from hexengine import __version__

            return str(__version__)
        except Exception:
            return "0.0.0"


def _numeric_parts(s: str) -> tuple[int, ...]:
    parts = [int(x) for x in re.findall(r"\d+", s)]
    return tuple(parts) if parts else (0,)


def server_is_newer_than_client(server: str, client: str) -> bool:
    """True if `server` version sorts after `client` (simple numeric segment compare)."""
    return _numeric_parts(server) > _numeric_parts(client)
