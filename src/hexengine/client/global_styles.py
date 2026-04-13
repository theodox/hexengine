"""
Inject global CSS from the server when a scenario adds layers beyond hexes.css.

Default presentation lives in `hexes.css`; we only touch the DOM when `[styles]`
(or a non-default base sheet) supplies something to load. This avoids an extra
stylesheet fetch and keeps Pyodide/DOM edge cases from breaking state updates.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from ..document import js, jsnull
from ..scenarios.schema import DEFAULT_GLOBAL_BASE_CSS_FILE

_BASE_LINK_ID = "hexengine-styles-base"
_SCENARIO_LINK_ID = "hexengine-styles-scenario-file"
_SCENARIO_STYLE_ID = "hexengine-styles-scenario-inline"

_logger = logging.getLogger("global_styles")


def _norm_href(href: str) -> str:
    return str(href).replace("\\", "/").strip()


def _remove_by_id(doc, element_id: str) -> None:
    el = doc.getElementById(element_id)
    # Pyodide: missing elements are JsNull, not Python None — `el is None` is false.
    if el is None or el is jsnull:
        return
    parent = el.parentNode
    if parent is None or parent is jsnull:
        return
    parent.removeChild(el)


def apply_global_styles(config: Mapping[str, Any]) -> None:
    """
    Apply `GlobalStylesConfig.to_wire_dict()` from StateUpdate.

    No-op (after clearing prior injections) when only the default base path is
    present with no `css` / `css_file` — `hexes.css` already defines layout.
    """
    doc = js.document

    for id_ in (_BASE_LINK_ID, _SCENARIO_LINK_ID, _SCENARIO_STYLE_ID):
        _remove_by_id(doc, id_)

    base_href = config.get("base_css_file") or DEFAULT_GLOBAL_BASE_CSS_FILE
    base_norm = _norm_href(base_href)
    default_norm = _norm_href(DEFAULT_GLOBAL_BASE_CSS_FILE)
    css_file = config.get("css_file")
    css_inline = config.get("css")
    has_inline = css_inline is not None and str(css_inline).strip()

    needs_injection = bool(css_file) or bool(has_inline) or base_norm != default_norm

    if not needs_injection:
        return

    parent = doc.body if doc.body else doc.head

    base_el = doc.createElement("link")
    base_el.id = _BASE_LINK_ID
    base_el.rel = "stylesheet"
    base_el.setAttribute("href", str(base_href))
    parent.appendChild(base_el)

    if css_file:
        link_s = doc.createElement("link")
        link_s.id = _SCENARIO_LINK_ID
        link_s.rel = "stylesheet"
        link_s.setAttribute("href", str(css_file))
        parent.appendChild(link_s)

    if has_inline:
        style_el = doc.createElement("style")
        style_el.id = _SCENARIO_STYLE_ID
        style_el.innerHTML = str(css_inline)
        parent.appendChild(style_el)


def apply_global_styles_safe(config: Mapping[str, Any]) -> None:
    """Like `apply_global_styles` but never raises (logs instead)."""
    try:
        apply_global_styles(config)
    except Exception:
        _logger.exception("apply_global_styles failed")
