"""
Small DOM helpers shared by UI modules.

Pyodide/JS interop sometimes produces JsNull instead of Python None; these helpers
avoid repeating those checks at call sites.
"""

from __future__ import annotations

from typing import Any

from ..document import jsnull


def safe_remove_child(parent: Any, child: Any) -> bool:
    """
    Try to remove `child` from `parent`.

    Returns True if a remove was attempted successfully, False if it was skipped
    or failed (never raises).
    """
    if parent is None or parent is jsnull or child is None or child is jsnull:
        return False
    try:
        parent.removeChild(child)
        return True
    except Exception:
        return False


__all__ = ["safe_remove_child"]

