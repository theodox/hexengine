import logging
from collections.abc import Iterable
from typing import Any

from ..document import js, jsnull
from ..hexes.types import Hex
from ..units import DisplayUnit
from .canvas_layer import CanvasLayer
from .handler import MouseHandler
from .layout import HexLayout
from .svg_layer import SVGLayer
from .unit_layer import UnitLayer


class Map:
    """
    A canvas for drawing hexagons.
    """

    def __init__(
        self,
        container_element: js.HTMLElement,
        canvas_element: js.HTMLCanvasElement,
        svg_element: js.SVGElement,
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
        if self._transform_root is None:
            logging.getLogger(__name__).error(
                "Missing #map-world wrapper; pan/zoom will not apply. Update hexes.html."
            )

        self._canvas_layer = CanvasLayer(
            canvas_element, self._hex_layout, self._hex_color, self._hex_stroke
        )
        self._svg_layer = SVGLayer(
            svg_element, self._hex_layout, self._hex_color, self._hex_stroke
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
            svg_element,
            unit_element,
        ):
            if el is not None:
                el.style.transform = ""

        self._clamp_pan()
        self._apply_transform()

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

    @property
    def canvas_layer(self) -> CanvasLayer:
        return self._canvas_layer

    @property
    def svg_layer(self) -> SVGLayer:
        return self._svg_layer

    @property
    def unit_layer(self) -> UnitLayer:
        return self._unit_layer

    def draw_hex(self, hex: Hex, cls="highlight"):
        self._svg_layer.draw_hexes([hex], cls=cls)

    def draw_hexes(self, hexes: Iterable[Hex], cls="highlight"):
        self._svg_layer.draw_hexes(hexes, cls=cls)

    def draw_bg_hexes(self, hexes: Iterable[Hex], fill="white", stroke="black"):
        for hex in hexes:
            self.draw_bg_hex(hex, fill=fill, stroke=stroke)

    def draw_bg_hex(self, hex: Hex, fill="white", stroke="black"):
        points = self._hex_layout.hex_corners(hex)
        points.append(points[0])  # Close the hexagon
        self.canvas.context.beginPath()
        self.canvas.context.strokeStyle = stroke
        self.canvas.context.fillStyle = fill
        for p in points:
            self.canvas.context.lineTo(*p)
            self.canvas.context.stroke()
        self.canvas.context.closePath()
        self.canvas.context.fill()

    def add_unit(self, unit: DisplayUnit):
        self._unit_layer.add_unit(unit)

    def refresh(self) -> None:
        """
        Refresh the map after a resize or zoom.
        Updates canvas dimensions, CSS variables, and redraws the canvas layer.
        Note: Unit positions should be refreshed separately via DisplayManager.
        """
        # Redraw canvas with new dimensions
        self._canvas_layer.redraw()

        self._set_unit_css_vars()

        self._clamp_pan()
        self._apply_transform()

        unit_size = int(self._hex_layout.size * self._unit_size_multiplier) - 2
        logging.getLogger().info(
            f"Map refreshed: hex_size={self._hex_layout.size}, unit_size={unit_size}"
        )

    def _set_unit_css_vars(self) -> None:
        unit_size = max(1, int(self._hex_layout.size * self._unit_size_multiplier) - 2)
        js.document.documentElement.style.setProperty("--unit-width", f"{unit_size}px")
        js.document.documentElement.style.setProperty("--unit-height", f"{unit_size}px")

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

        self._hex_layout = HexLayout(
            self._hex_size,
            self._hex_size + self._hex_margin,
            self._hex_size + self._hex_margin,
        )

        c = self._canvas_layer.canvas
        c.setAttribute("data-hexsize", str(self._hex_size))
        c.setAttribute("data-hexcolor", self._hex_color)
        c.setAttribute("data-hexstroke", str(self._hex_stroke))
        c.setAttribute("data-hexmargin", str(int(self._hex_margin)))

        self._canvas_layer._hex_layout = self._hex_layout
        self._canvas_layer.hex_color = self._hex_color
        self._canvas_layer.hex_stroke = self._hex_stroke

        self._svg_layer._hex_layout = self._hex_layout
        self._svg_layer._hex_color = self._hex_color
        self._svg_layer._hex_stroke = self._hex_stroke

        self._unit_layer._hex_layout = self._hex_layout
        self._unit_layer._hex_color = self._hex_color
        self._unit_layer._hex_stroke = self._hex_stroke

        for handler in (
            self._dragHandler,
            self._mouse_downHandler,
            self._mouse_upHandler,
        ):
            handler._layout = self._hex_layout

        if self._bg_element is not None:
            self._bg_element.setAttribute("src", m.background)

        self.reset_view()
        self.refresh()

    def _map_content_size(self) -> tuple[float, float]:
        """Drawable size in map pixels (matches canvas / stacked layers)."""
        c = self._canvas_layer.canvas
        return float(c.width), float(c.height)

    def _map_viewport_size(self) -> tuple[float, float]:
        """Visible map area in CSS pixels (#map-world or container fallback)."""
        if self._transform_root is not None:
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
        if self._transform_root is not None:
            self._transform_root.style.transform = transform
        else:
            if self._bg_element:
                self._bg_element.style.transform = transform
            self._canvas_layer.canvas.style.transform = transform
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
