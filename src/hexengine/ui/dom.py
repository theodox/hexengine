"""
Small DOM helpers shared by UI modules.

Pyodide/JS interop sometimes produces JsNull instead of Python None; these helpers
avoid repeating those checks at call sites.
"""

from __future__ import annotations

from typing import Any

from ..wire_interop import js_nullish


def safe_remove_child(parent: Any, child: Any) -> bool:
    """
    Try to remove `child` from `parent`.

    Returns True if a remove was attempted successfully, False if it was skipped
    or failed (never raises).
    """
    if js_nullish(parent) or js_nullish(child):
        return False
    try:
        parent.removeChild(child)
        return True
    except Exception:
        return False


def apply_css_classes(element: Any, class_str: str | None, *, base: str = "") -> None:
    """Set ``base`` class then add each token from ``class_str`` (space-separated)."""
    if js_nullish(element):
        return
    element.className = str(base).strip() if base else ""
    raw = "" if class_str is None else str(class_str).strip()
    if not raw:
        return
    for token in raw.split():
        if token:
            element.classList.add(token)


__all__ = ["apply_css_classes", "safe_remove_child"]
