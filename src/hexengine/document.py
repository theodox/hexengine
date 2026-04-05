import logging

import js  # pyright: ignore[reportMissingImports]
from pyodide.ffi import create_proxy, jsnull  # pyright: ignore[reportMissingImports]


def element(id: str) -> js.HTMLElement:
    logging.getLogger().debug(f"Retrieving element with id '{id}'")
    assert id is not None and id != "", "Element id must be a non-empty string"
    result = js.document.getElementById(id)
    assert result is not jsnull, f"Element with id '{id}' not found"
    return result


__all__ = ["element", "js", "jsnull", "create_proxy"]
