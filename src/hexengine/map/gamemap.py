from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from ..document import js, js_nullish, js_present, jsnull
from ..hexes.edges import (
    EdgeKey,
    polyline_vertices_for_vertex_adjacent_edge_keys,
    shared_edge_side_midpoint,
)
from ..hexes.types import Hex, HexColRow
from ..state.game_state import BoardEdgeFeature, GameState
from .canvas_layer import CanvasLayer, TerrainOverlayLayer
from .handler import MouseHandler
from .layout import HexLayout, unit_display_pixel_size
from .svg_layer import SVGLayer
from .unit_layer import UnitLayer

if TYPE_CHECKING:
    from ..units.graphics import DisplayUnit


def _edge_keys_share_one_hex(a: EdgeKey, b: EdgeKey) -> bool:
    """True if two undirected edges are consecutive on a hex spine (share exactly one hex)."""
    sa = {a.hex_low, a.hex_high}
    sb = {b.hex_low, b.hex_high}
    return len(sa & sb) == 1


def _edge_feature_logical_group_stem(feature_id: str) -> str:
    """Stem before '~' digits (e.g. river~3 → river); used to avoid merging distinct features."""
    if "~" in feature_id:
        stem, suf = feature_id.rsplit("~", 1)
        if suf.isdigit():
            return stem
    return feature_id


def _edge_features_mergeable_render(a: BoardEdgeFeature, b: BoardEdgeFeature) -> bool:
    """Only chain edge rows that look like the same overlay (tags + stroke hints)."""
    return (
        a.tags == b.tags
        and a.stroke_width == b.stroke_width
        and a.stroke_color == b.stroke_color
        and a.stroke_dash == b.stroke_dash
        and a.layer_z == b.layer_z
        and _edge_feature_logical_group_stem(a.feature_id)
        == _edge_feature_logical_group_stem(b.feature_id)
    )


def _svg_apply_feature_stroke(
    el: Any,
    *,
    stroke_color: str | None,
    stroke_width: float | None,
    stroke_dash: str | None,
) -> None:
    """Presentation attributes for per-feature stroke (overrides CSS defaults when set)."""
    if stroke_color is not None:
        el.setAttribute("stroke", str(stroke_color))
    if stroke_width is not None:
        el.setAttribute("stroke-width", str(float(stroke_width)))
    if stroke_dash is not None:
        el.setAttribute("stroke-dasharray", str(stroke_dash))


class Map:
    """
    A canvas for drawing hexagons.
    """

    _MAP_BG_CLASS_CROP = "map-bg--crop"
    _MAP_BG_CLASS_STRETCH = "map-bg--stretch"

    def __init__(
        self,
        container_element: js.HTMLElement,
        canvas_element: js.HTMLCanvasElement,
        terrain_canvas: js.HTMLCanvasElement,
        svg_element: js.SVGElement,
        marker_element: js.SVGElement,
        unit_element: js.SVGElement,
    ):
        self._container = container_element

        self._hex_size = canvas_element.getAttribute("data-hexsize")
        self._hex_color = canvas_element.getAttribute("data-hexcolor")
        _stroke_attr = canvas_element.getAttribute("data-hexstroke")
        _margin_attr = canvas_element.getAttribute("data-hexmargin")
        self._hex_stroke = (
            int(float(_stroke_attr)) if _stroke_attr not in (None, "", jsnull) else 1
        )
        self._hex_margin = (
            float(_margin_attr) if _margin_attr not in (None, "", jsnull) else 0.0
        )
        logging.getLogger().warning(
            f"Hex size: {self._hex_size}, color: {self._hex_color}, stroke: {self._hex_stroke}"
        )

        if self._hex_size is not None:
            self._hex_size = float(self._hex_size)
        else:
            self._hex_size = 24.0

        self._unit_size_multiplier = 1.5

        self._hex_layout = HexLayout(
            self._hex_size,
            self._hex_size + self._hex_margin,
            self._hex_size + self._hex_margin,
        )

        self._set_unit_css_vars()

        # Zoom and pan state
        self._zoom_level = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._min_zoom = 0.5
        self._max_zoom = 3.0

        self._bg_element = js.document.getElementById("map-bg")
        self._transform_root = js.document.getElementById("map-world")
        if js_nullish(self._transform_root):
            logging.getLogger(__name__).error(
                "Missing #map-world wrapper; pan/zoom will not apply. Update hexes.html."
            )
        self._overlay_layer: Any = None

        self._canvas_layer = CanvasLayer(
            canvas_element, self._hex_layout, self._hex_color, self._hex_stroke
        )
        self._terrain_layer = TerrainOverlayLayer(
            terrain_canvas, self._hex_layout, visible=True
        )
        self._svg_layer = SVGLayer(
            svg_element, self._hex_layout, self._hex_color, self._hex_stroke
        )
        self._marker_layer = SVGLayer(
            marker_element, self._hex_layout, self._hex_color, self._hex_stroke
        )
        self._unit_layer = UnitLayer(
            unit_element, self._hex_layout, self._hex_color, self._hex_stroke
        )

        self._dragHandler = MouseHandler(
            self._container, "mousemove", self._hex_layout, self
        )
        self._mouse_downHandler = MouseHandler(
            self._container, "mousedown", self._hex_layout, self
        )
        self._mouse_upHandler = MouseHandler(
            self._container, "mouseup", self._hex_layout, self
        )

        # Legacy: transform was applied per-layer; clear so only #map-world carries pan/zoom.
        for el in (
            self._bg_element,
            canvas_element,
            terrain_canvas,
            svg_element,
            marker_element,
            unit_element,
        ):
            if js_present(el):
                el.style.transform = ""

        self._clamp_pan()
        self._apply_transform()
        self._sync_overlay_svg_size()
        self._sync_map_bg_dom_size()

        #: Odd-q col,row labels on #map-svg (toggle with Alt+H in Game).
        self._hex_address_labels_visible = False

    @property
    def on_drag(self):
        return self._dragHandler

    @property
    def on_mouse_down(self):
        return self._mouse_downHandler

    @property
    def on_mouse_up(self):
        return self._mouse_upHandler

    @property
    def hex_size(self) -> float:
        return self._hex_size

    @property
    def hex_layout(self) -> HexLayout:
        return self._hex_layout

    def map_space_to_container_pixel(self, x: float, y: float) -> tuple[float, float]:
        """
        Map-space pixel (e.g. from HexLayout.hex_to_pixel) to coordinates in
        #map-container space under the current translate(pan) scale(zoom)
        on #map-world (see _clamp_pan docstring: zoom * m + pan).
        """
        z = self._zoom_level
        return (float(x) * z + self._pan_x, float(y) * z + self._pan_y)

    def ensure_overlay_layer(self) -> Any:
        """
        Single absolutely positioned layer inside #map-world for title-driven overlays.

        Map-space left / top match HexLayout.hex_to_pixel; pan/zoom apply via
        the parent transform.
        """
        if js_nullish(self._transform_root):
            return None
        if self._overlay_layer is None:
            div = js.document.createElement("div")
            div.id = "hexengine-map-overlays"
            div.style.position = "absolute"
            div.style.left = "0"
            div.style.top = "0"
            div.style.width = "100%"
            div.style.height = "100%"
            div.style.zIndex = "400"
            self._transform_root.appendChild(div)
            self._overlay_layer = div
        return self._overlay_layer

    @property
    def unit_size_multiplier(self) -> float:
        return self._unit_size_multiplier

    @property
    def canvas_layer(self) -> CanvasLayer:
        return self._canvas_layer

    @property
    def svg_layer(self) -> SVGLayer:
        return self._svg_layer

    @property
    def unit_layer(self) -> UnitLayer:
        return self._unit_layer

    @property
    def marker_layer(self) -> SVGLayer:
        return self._marker_layer

    @property
    def terrain_overlay_visible(self) -> bool:
        return self._terrain_layer.visible

    def set_terrain_overlay_visible(self, visible: bool) -> None:
        self._terrain_layer.set_visible(visible)

    def redraw_terrain_overlay(self, state: GameState) -> None:
        """Repaint terrain tints from board locations (hex_color)."""
        self._terrain_layer.set_layout(self._hex_layout)
        self._terrain_layer.redraw_terrain(state.board.locations.values())

    def redraw_map_features(self, state: GameState) -> None:
        """Draw edge and centerline primitives from board state (SVG under interaction highlights)."""
        svg = self._svg_layer._svg
        old = js.document.getElementById("hexengine-map-features")
        if js_present(old):
            old.remove()
        if not state.board.edge_features and not state.board.linear_features:
            return
        g = js.document.createElementNS("http://www.w3.org/2000/svg", "g")
        g.setAttribute("id", "hexengine-map-features")
        g.setAttribute("class", "hexengine-map-features")
        if svg.firstChild is not None:
            svg.insertBefore(g, svg.firstChild)
        else:
            svg.appendChild(g)
        layout = self._hex_layout
        edge_feats = state.board.edge_features

        ei = 0
        while ei < len(edge_feats):
            ej = ei + 1
            while ej < len(edge_feats):
                prev, cur = edge_feats[ej - 1], edge_feats[ej]
                if not _edge_keys_share_one_hex(prev.edge_key, cur.edge_key):
                    break
                if not _edge_features_mergeable_render(prev, cur):
                    break
                ej += 1
            group = edge_feats[ei:ej]
            g0 = group[0]
            keys = tuple(f.edge_key for f in group)
            pts = polyline_vertices_for_vertex_adjacent_edge_keys(layout, keys)
            if len(pts) >= 2:
                poly = js.document.createElementNS("http://www.w3.org/2000/svg", "polyline")
                poly.setAttribute(
                    "points",
                    " ".join(f"{float(x)},{float(y)}" for x, y in pts),
                )
                poly.setAttribute("class", "hexengine-map-edge-feature")
                poly.setAttribute("fill", "none")
                _svg_apply_feature_stroke(
                    poly,
                    stroke_color=g0.stroke_color,
                    stroke_width=g0.stroke_width,
                    stroke_dash=g0.stroke_dash,
                )
                g.appendChild(poly)
            else:
                for feat in group:
                    (x0, y0), (x1, y1) = shared_edge_side_midpoint(layout, feat.edge_key)
                    line = js.document.createElementNS(
                        "http://www.w3.org/2000/svg", "line"
                    )
                    line.setAttribute("x1", str(float(x0)))
                    line.setAttribute("y1", str(float(y0)))
                    line.setAttribute("x2", str(float(x1)))
                    line.setAttribute("y2", str(float(y1)))
                    line.setAttribute("class", "hexengine-map-edge-feature")
                    _svg_apply_feature_stroke(
                        line,
                        stroke_color=feat.stroke_color,
                        stroke_width=feat.stroke_width,
                        stroke_dash=feat.stroke_dash,
                    )
                    g.appendChild(line)
            ei = ej
        for lf in state.board.linear_features:
            pts: list[str] = []
            for h in lf.path_hexes:
                x, y = layout.hex_to_pixel(h)
                pts.append(f"{float(x)},{float(y)}")
            poly = js.document.createElementNS("http://www.w3.org/2000/svg", "polyline")
            poly.setAttribute("points", " ".join(pts))
            poly.setAttribute("class", "hexengine-map-linear-feature")
            poly.setAttribute("fill", "none")
            _svg_apply_feature_stroke(
                poly,
                stroke_color=lf.stroke_color,
                stroke_width=lf.stroke_width,
                stroke_dash=lf.stroke_dash,
            )
            g.appendChild(poly)

    def draw_hex(self, hex: Hex, cls="highlight"):
        self._svg_layer.draw_hexes([hex], cls=cls)

    def draw_hexes(self, hexes: Iterable[Hex], cls="highlight"):
        self._svg_layer.draw_hexes(hexes, cls=cls)

    def draw_bg_hexes(self, hexes: Iterable[Hex], fill="white", stroke="black"):
        for hex in hexes:
            self.draw_bg_hex(hex, fill=fill, stroke=stroke)

    def draw_bg_hex(self, hex: Hex, fill="white", stroke="black"):
        corners = self._hex_layout.hex_corners(hex)
        if len(corners) < 3:
            return
        ctx = self.canvas.context
        ctx.beginPath()
        ctx.moveTo(corners[0][0], corners[0][1])
        for x, y in corners[1:]:
            ctx.lineTo(x, y)
        ctx.closePath()
        ctx.strokeStyle = stroke
        ctx.fillStyle = fill
        ctx.fill()
        ctx.stroke()

    def add_unit(self, unit: DisplayUnit):
        self._unit_layer.add_unit(unit)

    def _sync_overlay_svg_size(self) -> None:
        """Match terrain canvas and hex/unit SVG pixel size to the map grid canvas."""
        c = self._canvas_layer.canvas
        w, h = int(c.width), int(c.height)
        self._terrain_layer.sync_size(w, h)
        for svg in (
            self._svg_layer._svg,
            self._marker_layer._svg,
            self._unit_layer._svg,
        ):
            svg.setAttribute("width", str(w))
            svg.setAttribute("height", str(h))
            svg.style.width = f"{w}px"
            svg.style.height = f"{h}px"

    def _sync_map_world_dom_size(self) -> None:
        """
        Size #map-world to the grid canvas pixel box so the layout is not a huge CSS
        aspect-ratio viewport with a small hex grid in the corner.
        """
        if js_nullish(self._transform_root):
            return
        c = self._canvas_layer.canvas
        w, h = int(c.width), int(c.height)
        if (
            self._canvas_layer._fixed_canvas_w is not None
            and self._canvas_layer._fixed_canvas_h is not None
        ):
            self._transform_root.style.width = f"{w}px"
            self._transform_root.style.height = f"{h}px"
        else:
            self._transform_root.style.width = ""
            self._transform_root.style.height = ""

    def _sync_map_bg_dom_size(self) -> None:
        """
        Match `#map-bg` pixel box to the grid canvas (same as SVG overlays).

        When left at `width/height: 100%`, the layer sizes to `#map-world`, which may
        still be the wide `aspect-ratio` strip—so `background-size: cover` scales the
        art to that large box. Explicit px ties the background to the hex map extent.
        """
        if js_nullish(self._bg_element):
            return
        c = self._canvas_layer.canvas
        w, h = int(c.width), int(c.height)
        st = self._bg_element.style
        if (
            self._canvas_layer._fixed_canvas_w is not None
            and self._canvas_layer._fixed_canvas_h is not None
        ):
            st.setProperty("width", f"{w}px")
            st.setProperty("height", f"{h}px")
        else:
            st.removeProperty("width")
            st.removeProperty("height")

    def refresh(self) -> None:
        """
        Refresh the map after a resize or zoom.
        Updates canvas dimensions, CSS variables, and redraws the canvas layer.
        Note: Unit positions should be refreshed separately via DisplayManager.
        """
        # Redraw canvas with new dimensions
        self._canvas_layer.redraw()
        self._sync_overlay_svg_size()
        self._sync_map_world_dom_size()
        self._sync_map_bg_dom_size()

        self._set_unit_css_vars()

        self._clamp_pan()
        self._apply_transform()

        unit_size = unit_display_pixel_size(
            self._hex_layout.size, self._unit_size_multiplier
        )
        logging.getLogger().info(
            f"Map refreshed: hex_size={self._hex_layout.size}, unit_size={unit_size}"
        )
        if self._hex_address_labels_visible:
            self.sync_hex_address_labels()

    _HEX_ADDRESS_LABELS_SVG_ID = "hexengine-hex-address-labels"

    def toggle_hex_address_labels(self) -> bool:
        """Toggle odd-q col,row text on each grid hex; returns new visibility."""
        self._hex_address_labels_visible = not self._hex_address_labels_visible
        self.sync_hex_address_labels()
        return self._hex_address_labels_visible

    def sync_hex_address_labels(self) -> None:
        """Remove or rebuild the address label group on #map-svg (map-space coords)."""
        svg = self._svg_layer._svg
        old = js.document.getElementById(self._HEX_ADDRESS_LABELS_SVG_ID)
        if js_present(old):
            old.remove()
        if not self._hex_address_labels_visible:
            return
        hexes = self._canvas_layer.grid_hexes_for_labels()
        if not hexes:
            return
        g = js.document.createElementNS(SVGLayer.SVG, "g")
        g.setAttribute("id", self._HEX_ADDRESS_LABELS_SVG_ID)
        g.setAttribute("class", "hexengine-hex-address-labels")
        layout = self._hex_layout
        for hx in hexes:
            cr = HexColRow.from_hex(hx)
            x, y = layout.hex_to_pixel(hx)
            t = js.document.createElementNS(SVGLayer.SVG, "text")
            t.setAttribute("x", str(x))
            t.setAttribute("y", str(y))
            t.setAttribute("text-anchor", "middle")
            t.setAttribute("dominant-baseline", "central")
            t.setAttribute("font-size", "11")
            t.textContent = f"{cr.col},{cr.row}"
            g.appendChild(t)
        svg.appendChild(g)

    def _set_unit_css_vars(self) -> None:
        unit_size = unit_display_pixel_size(
            self._hex_layout.size, self._unit_size_multiplier
        )
        js.document.documentElement.style.setProperty("--unit-width", f"{unit_size}px")
        js.document.documentElement.style.setProperty("--unit-height", f"{unit_size}px")

    def _apply_map_background(self, m: Any) -> None:
        """Set `#map-bg` image URL and crop vs stretch via CSS classes (see hexes.css)."""
        if js_nullish(self._bg_element):
            return
        el = self._bg_element
        el.classList.remove(self._MAP_BG_CLASS_CROP, self._MAP_BG_CLASS_STRETCH)
        el.classList.add(
            self._MAP_BG_CLASS_CROP
            if m.background_crop_to_map
            else self._MAP_BG_CLASS_STRETCH
        )

        url = str(m.background).strip().replace("\\", "/")
        st = el.style
        if not url:
            st.setProperty("background-image", "none")
            return
        escaped = url.replace("\\", "\\\\").replace('"', '\\"')
        st.setProperty("background-image", f'url("{escaped}")')

    def apply_map_display(self, config: dict[str, Any]) -> None:
        """
        Apply scenario map presentation (hex geometry, grid style, background, unit scale).

        Resets pan/zoom, redraws the grid, and updates CSS unit variables. Call
        DisplayManager.adopt_hex_layout() after this if units already exist.
        """
        from ..scenarios.schema import MapDisplayConfig

        m = MapDisplayConfig.from_wire_dict(config)
        self._hex_size = m.hex_size
        self._hex_margin = float(m.hex_margin)
        self._hex_color = m.hex_color
        self._hex_stroke = int(m.hex_stroke)
        self._unit_size_multiplier = float(m.unit_size_multiplier)

        # (n_cols, n_rows, origin_col, origin_row) odd-q, same space as scenario positions.
        grid_spec: tuple[int, int, int, int] | None = None
        if m.hex_columns is not None and m.hex_rows is not None:
            grid_spec = (
                m.hex_columns,
                m.hex_rows,
                m.hex_origin_i,
                m.hex_origin_j,
            )

        grid_hex_models: list[Hex] | None = None
        if m.grid_hexes:
            grid_hex_models = [Hex(t[0], t[1], t[2]) for t in m.grid_hexes]

        self._canvas_layer.hex_color = self._hex_color
        self._canvas_layer.set_scenario_grid(
            grid_spec,
            self._hex_size,
            self._hex_margin,
            self._hex_stroke,
            grid_hexes=grid_hex_models,
        )
        self._hex_layout = self._canvas_layer._hex_layout

        c = self._canvas_layer.canvas
        c.setAttribute("data-hexsize", str(self._hex_size))
        c.setAttribute("data-hexcolor", self._hex_color)
        c.setAttribute("data-hexstroke", str(self._hex_stroke))
        c.setAttribute("data-hexmargin", str(int(self._hex_margin)))

        self._svg_layer._hex_layout = self._hex_layout
        self._svg_layer._hex_color = self._hex_color
        self._svg_layer._hex_stroke = self._hex_stroke

        self._terrain_layer.set_layout(self._hex_layout)
        self._terrain_layer.set_line_style(
            m.terrain_overlay_line_color,
            m.terrain_overlay_line_width,
        )

        self._unit_layer._hex_layout = self._hex_layout
        self._unit_layer._hex_color = self._hex_color
        self._unit_layer._hex_stroke = self._hex_stroke

        for handler in (
            self._dragHandler,
            self._mouse_downHandler,
            self._mouse_upHandler,
        ):
            handler._layout = self._hex_layout

        self._apply_map_background(m)

        self.reset_view()
        self.refresh()

    def _map_content_size(self) -> tuple[float, float]:
        """Drawable size in map pixels (matches canvas / stacked layers)."""
        c = self._canvas_layer.canvas
        return float(c.width), float(c.height)

    def _map_viewport_size(self) -> tuple[float, float]:
        """Visible map area in CSS pixels (#map-world or container fallback)."""
        if js_present(self._transform_root):
            w = float(self._transform_root.clientWidth)
            h = float(self._transform_root.clientHeight)
            if w > 0 and h > 0:
                return w, h
        rect = self._container.getBoundingClientRect()
        return float(rect.width), float(rect.height)

    def _clamp_pan(self) -> None:
        """
        Keep scaled map content overlapping the viewport (no infinite empty pan).

        With transform translate(pan) scale(zoom), a map point m appears at zoom*m + pan.
        Content occupies [0, mw] x [0, mh] in map space.
        """
        vw, vh = self._map_viewport_size()
        mw, mh = self._map_content_size()
        z = self._zoom_level
        sw, sh = z * mw, z * mh

        def clamp_axis(pan: float, v: float, s: float) -> float:
            if v <= 0 or s <= 0:
                return pan
            if s >= v:
                lo, hi = v - s, 0.0
            else:
                lo, hi = 0.0, v - s
            return max(lo, min(hi, pan))

        self._pan_x = clamp_axis(self._pan_x, vw, sw)
        self._pan_y = clamp_axis(self._pan_y, vh, sh)

    def _apply_transform(self) -> None:
        """
        Apply pan/zoom once on #map-world so bg, canvas, hex SVG, and units stay in sync.
        Map coordinates inside children are unchanged; only the wrapper transforms.
        """
        transform = (
            f"translate({self._pan_x}px, {self._pan_y}px) scale({self._zoom_level})"
        )
        if js_present(self._transform_root):
            self._transform_root.style.transform = transform
        else:
            if js_present(self._bg_element):
                self._bg_element.style.transform = transform
            self._canvas_layer.canvas.style.transform = transform
            self._terrain_layer._canvas.style.transform = transform
            self._svg_layer._svg.style.transform = transform
            self._unit_layer._svg.style.transform = transform

        log = logging.getLogger(__name__)
        if log.isEnabledFor(logging.DEBUG):
            log.debug(
                "Applied transform: zoom=%.2f, pan=(%.1f, %.1f)",
                self._zoom_level,
                self._pan_x,
                self._pan_y,
            )

    def set_zoom(
        self, zoom_level: float, center_x: float = None, center_y: float = None
    ) -> None:
        """
        Set zoom level, optionally zooming toward a specific point.

        Args:
            zoom_level: New zoom level (clamped to min/max)
            center_x: X coordinate to zoom toward (in screen space)
            center_y: Y coordinate to zoom toward (in screen space)
        """
        # Clamp zoom level
        old_zoom = self._zoom_level
        self._zoom_level = max(self._min_zoom, min(self._max_zoom, zoom_level))

        # If zooming toward a point, adjust pan to keep that point stationary
        if center_x is not None and center_y is not None:
            # Calculate the point's position in the map coordinate system
            zoom_ratio = self._zoom_level / old_zoom

            # Adjust pan to zoom toward the specified point
            self._pan_x = center_x - (center_x - self._pan_x) * zoom_ratio
            self._pan_y = center_y - (center_y - self._pan_y) * zoom_ratio

        self._clamp_pan()
        self._apply_transform()

    def adjust_zoom(
        self, delta: float, center_x: float = None, center_y: float = None
    ) -> None:
        """
        Adjust zoom level by a delta amount.

        Args:
            delta: Amount to change zoom (positive = zoom in, negative = zoom out)
            center_x: X coordinate to zoom toward
            center_y: Y coordinate to zoom toward
        """
        self.set_zoom(self._zoom_level + delta, center_x, center_y)

    def set_pan(self, pan_x: float, pan_y: float) -> None:
        """
        Set pan offset.

        Args:
            pan_x: X offset in pixels
            pan_y: Y offset in pixels
        """
        self._pan_x = pan_x
        self._pan_y = pan_y
        self._clamp_pan()
        self._apply_transform()

    def adjust_pan(self, delta_x: float, delta_y: float) -> None:
        """
        Adjust pan by a delta amount.

        Args:
            delta_x: Change in X offset
            delta_y: Change in Y offset
        """
        self.set_pan(self._pan_x + delta_x, self._pan_y + delta_y)

    @property
    def zoom_level(self) -> float:
        """Get current zoom level."""
        return self._zoom_level

    @property
    def pan_offset(self) -> tuple[float, float]:
        """Get current pan offset."""
        return (self._pan_x, self._pan_y)

    def reset_view(self) -> None:
        """
        Reset zoom and pan to default values.
        """
        self._zoom_level = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._clamp_pan()
        self._apply_transform()
        logging.getLogger().info("View reset to default")
