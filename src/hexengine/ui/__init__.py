"""UI components for the hex engine (browser DOM helpers + server-safe display markup)."""

from __future__ import annotations

__all__ = ["MapOverlayManager", "PopupManager"]


def __getattr__(name: str):
    """Lazy imports so ``hexengine.ui.display`` is safe on the server (no ``js``)."""
    if name == "MapOverlayManager":
        from .map_overlays import MapOverlayManager

        return MapOverlayManager
    if name == "PopupManager":
        from .popups import PopupManager

        return PopupManager
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
