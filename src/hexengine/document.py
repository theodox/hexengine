from __future__ import annotations

import logging

import js  # pyright: ignore[reportMissingImports]
from pyodide.ffi import create_proxy  # pyright: ignore[reportMissingImports]

from .wire_interop import js_nullish, js_present, jsnull, wire_str


def element(id: str) -> js.HTMLElement:
    logging.getLogger().debug(f"Retrieving element with id '{id}'")
    assert id is not None and id != "", "Element id must be a non-empty string"
    result = js.document.getElementById(id)
    assert js_present(result), f"Element with id '{id}' not found"
    return result


__all__ = [
    "create_proxy",
    "element",
    "js",
    "js_present",
    "js_nullish",
    "jsnull",
    "wire_str",
]
