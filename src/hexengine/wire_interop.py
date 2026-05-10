"""
Wire-format and Pyodide-friendly value coercions without importing the browser js module.

Server code (CPython) imports paths that need wire_str / js_nullish; keep those
definitions here so hexengine.document (which imports js) is not loaded on the server.
"""

from __future__ import annotations

from typing import Any

try:
    from pyodide.ffi import jsnull  # pyright: ignore[reportMissingImports]
except ImportError:

    class _JsNullSentinel:
        __slots__ = ()

    jsnull = _JsNullSentinel()


def js_nullish(value: Any) -> bool:
    """
    True for missing values that can appear as either Python None or js.null
    after DOM / JSON interop (Pyodide).
    """
    return value is None or value is jsnull


def js_present(value: Any) -> bool:
    """Inverse of js_nullish (readable guard for DOM nodes and hook payloads)."""
    return not js_nullish(value)


def wire_str(value: Any) -> str:
    """
    Coerce wire / JSON values to str in Pyodide-friendly way.

    JsProxy strings are not always isinstance(..., str); js.null stringifies
    to the unhelpful "JsNull" if passed through str() blindly.
    """
    if js_nullish(value):
        return ""
    if isinstance(value, str):
        return value
    to_py = getattr(value, "to_py", None)
    if callable(to_py):
        try:
            converted = to_py()
        except Exception:
            converted = value
        if js_nullish(converted):
            return ""
        if isinstance(converted, str):
            return converted
        value = converted
    return str(value)


__all__ = ["js_present", "js_nullish", "jsnull", "wire_str"]
