"""
Map package for hexengine.

This package provides components for rendering and interacting with hexagonal maps.
Pyodide-only modules (e.g. ``MouseHandler``, ``Map``) load on first attribute access
so CPython servers can import :mod:`hexengine.map.layout` without ``pyodide``.
"""

from __future__ import annotations

from .layout import HexLayout

__all__ = [
    "HexLayout",
    "Map",
    "MouseHandler",
]


def __getattr__(name: str):
    if name == "Map":
        from .gamemap import Map

        return Map
    if name == "MouseHandler":
        from .handler import MouseHandler

        return MouseHandler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
