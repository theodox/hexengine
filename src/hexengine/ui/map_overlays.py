"""
Map-space overlays: keyed DOM nodes under #map-world (pan/zoom with the board).

The server sends overlay rows on StateUpdate.map_overlays; the client syncs
them here. Presentation is title CSS; this module only creates/positions elements.
"""

from __future__ import annotations

import logging
from typing import Any

from ..document import js
from ..hexes.types import Hex
from ..map.gamemap import Map
from .dom import safe_remove_child

LOGGER = logging.getLogger(__name__)


class MapOverlayManager:
    """Create, update, and remove overlay elements from wire rows."""

    def __init__(self, game_map: Map) -> None:
        self._map = game_map
        self._dom_by_id: dict[str, Any] = {}

    def sync(self, rows: list[dict[str, Any]] | None) -> None:
        layer = self._map.ensure_overlay_layer()
        if layer is None:
            return

        want: dict[str, dict[str, Any]] = {}
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            oid = str(r.get("id", "")).strip()
            if not oid:
                continue
            want[oid] = r

        for oid in list(self._dom_by_id.keys()):
            if oid not in want:
                el = self._dom_by_id.pop(oid)
                ok = safe_remove_child(layer, el)
                if not ok:
                    LOGGER.debug("removeChild overlay %r failed", oid, exc_info=True)

        for oid, row in want.items():
            el = self._dom_by_id.get(oid)
            if el is not None:
                self._apply_row(el, row)
            else:
                new_el = self._create_element(row)
                if new_el is not None:
                    layer.appendChild(new_el)
                    self._dom_by_id[oid] = new_el

    def _hex_from_row(self, row: dict[str, Any]) -> Hex | None:
        hx = row.get("hex")
        if not isinstance(hx, dict):
            return None
        try:
            return Hex(int(hx["i"]), int(hx["j"]), int(hx["k"]))
        except Exception:
            return None

    def _apply_row(self, el: Any, row: dict[str, Any]) -> None:
        h = self._hex_from_row(row)
        if h is None:
            return
        mx, my = self._map.hex_layout.hex_to_pixel(h)
        el.style.left = f"{mx}px"
        el.style.top = f"{my}px"
        kind = str(row.get("kind", "glyph")).lower()
        if kind == "glyph":
            el.textContent = str(row.get("text", ""))

    def _create_element(self, row: dict[str, Any]) -> Any | None:
        kind = str(row.get("kind", "glyph")).lower()
        if kind != "glyph":
            return None
        h = self._hex_from_row(row)
        if h is None:
            return None
        mx, my = self._map.hex_layout.hex_to_pixel(h)
        div = js.document.createElement("div")
        div.setAttribute("data-overlay-id", str(row.get("id", "")))
        div.style.position = "absolute"
        div.style.left = f"{mx}px"
        div.style.top = f"{my}px"
        div.style.transform = "translate(-50%, -50%)"
        div.style.pointerEvents = "none"
        cc = row.get("css_class")
        if isinstance(cc, str) and cc.strip():
            div.className = f"hexengine-map-overlay hexengine-map-overlay--glyph {cc.strip()}"
        else:
            div.className = "hexengine-map-overlay hexengine-map-overlay--glyph"
        div.textContent = str(row.get("text", ""))
        return div


__all__ = ["MapOverlayManager"]
