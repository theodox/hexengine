"""
MarkerManager — map markers on a dedicated SVG layer below units.

Marker appearance is driven by `marker_graphics` templates (same wire shape as
`unit_graphics`) resolved through `creator_for_template` — parallel to how
`unit_graphics` + unit `type` define unit visuals.

`DisplayUnit` supports `set_glyph` / `set_caption` / `set_text` for live
updates; markers do not use that path yet (labels come from the template only).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..hexes.types import Hex, HexColRow
from ..units.graphics import DisplayUnit
from .svg_templates import creator_for_template

if TYPE_CHECKING:
    from ..map import Map


class MarkerManager:
    def __init__(self, map_canvas: Map) -> None:
        self._canvas = map_canvas
        self._marker_displays: dict[str, DisplayUnit] = {}
        self._marker_graphics_wire: dict[str, dict[str, Any]] = {}
        self.logger = logging.getLogger("marker_manager")

    def has_display(self, marker_id: str) -> bool:
        return marker_id in self._marker_displays

    def get_display(self, marker_id: str) -> DisplayUnit | None:
        return self._marker_displays.get(marker_id)

    def show_preview(
        self, marker_id: str, pixel_x: float, pixel_y: float, is_valid: bool
    ) -> None:
        display = self._marker_displays.get(marker_id)
        if not display:
            return
        display.display_at(pixel_x, pixel_y)
        display.enabled = is_valid

    def clear_preview(self, marker_id: str, committed_position: Hex) -> None:
        display = self._marker_displays.get(marker_id)
        if not display:
            return
        display.position = committed_position
        display.enabled = True

    def set_marker_hilite(self, marker_id: str | None) -> None:
        """Highlight at most one marker (selection / drag affordance)."""
        for mid, disp in self._marker_displays.items():
            disp.hilited = marker_id is not None and mid == marker_id

    def apply_marker_graphics(self, wire: dict[str, Any]) -> None:
        raw: Any = wire.to_py() if hasattr(wire, "to_py") else wire
        if not isinstance(raw, dict):
            raw = dict(raw)
        normalized: dict[str, dict[str, Any]] = {}
        for k, v in raw.items():
            if hasattr(v, "to_py"):
                v = v.to_py()
            normalized[str(k)] = dict(v) if v is not None else {}
        prev_sig = json.dumps(
            self._marker_graphics_wire, sort_keys=True, ensure_ascii=True
        )
        new_sig = json.dumps(normalized, sort_keys=True, ensure_ascii=True)
        if new_sig == prev_sig:
            return
        self._marker_graphics_wire = normalized
        # Rebuild existing markers with new templates
        for mid in list(self._marker_displays.keys()):
            self._remove_marker_display(mid)

    def sync_markers(self, markers: list[dict[str, Any]] | None) -> None:
        raw: Any = markers.to_py() if hasattr(markers, "to_py") else markers
        if not raw:
            # Remove all markers
            for mid in list(self._marker_displays.keys()):
                self._remove_marker_display(mid)
            return
        # Create/update active markers
        live_ids: set[str] = set()
        for m in list(raw):
            if hasattr(m, "to_py"):
                m = m.to_py()
            mid = str(m.get("id", ""))
            if not mid:
                continue
            live_ids.add(mid)
            active = bool(m.get("active", True))
            if not active:
                if mid in self._marker_displays:
                    self._remove_marker_display(mid)
                continue
            if mid not in self._marker_displays:
                self._create_marker_display(m)
            else:
                self._update_marker_display(mid, m)
        # Remove stale
        for mid in list(self._marker_displays.keys()):
            if mid not in live_ids:
                self._remove_marker_display(mid)

    def _get_creator(self, marker_type: str) -> Callable[[DisplayUnit], None] | None:
        tmpl = self._marker_graphics_wire.get(marker_type)
        if not tmpl:
            return None
        return creator_for_template(tmpl)

    def _create_marker_display(self, marker: dict[str, Any]) -> None:
        marker_id = str(marker.get("id"))
        marker_type = str(marker.get("type", ""))
        pos = marker.get("position")
        if (
            not marker_id
            or not marker_type
            or not isinstance(pos, list | tuple)
            or len(pos) != 2
        ):
            return
        creator = self._get_creator(marker_type)
        if creator is None:
            self.logger.warning("No marker graphics for type %r", marker_type)
            return

        display = DisplayUnit(
            unit_id=marker_id,
            unit_type=marker_type,
            layout=self._canvas.hex_layout,
            unit_size_multiplier=self._canvas.unit_size_multiplier,
        )
        creator(display)
        display.proxy.setAttribute("data-marker", marker_id)
        display.proxy.style.pointerEvents = "all"

        col, row = int(pos[0]), int(pos[1])
        h = Hex.from_hex_col_row(HexColRow(col=col, row=row))
        display.position = h
        display.visible = True

        self._canvas.marker_layer._svg.appendChild(display.proxy)
        self._marker_displays[marker_id] = display

    def _update_marker_display(self, marker_id: str, marker: dict[str, Any]) -> None:
        display = self._marker_displays[marker_id]
        pos = marker.get("position")
        if isinstance(pos, list | tuple) and len(pos) == 2:
            col, row = int(pos[0]), int(pos[1])
            h = Hex.from_hex_col_row(HexColRow(col=col, row=row))
            if display.position != h:
                display.position = h

    def _remove_marker_display(self, marker_id: str) -> None:
        d = self._marker_displays.get(marker_id)
        if d is None:
            return
        try:
            d.proxy.remove()
        except Exception:
            pass
        del self._marker_displays[marker_id]
