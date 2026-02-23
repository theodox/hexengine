import logging
from typing import Iterable

from ..document import js
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
        self._hex_stroke = int(canvas_element.getAttribute("data-hexstroke"))
        self._hex_margin = int(canvas_element.getAttribute("data-hexmargin"))
        logging.getLogger().warning(
            f"Hex size: {self._hex_size}, color: {self._hex_color}, stroke: {self._hex_stroke}"
        )

        if self._hex_size is not None:
            self._hex_size = float(self._hex_size)
        else:
            self._hex_size = 24

        self._hex_layout = HexLayout(
            self._hex_size,
            self._hex_size + self._hex_margin,
            self._hex_size + self._hex_margin,
        )

        # Set CSS variables for unit sizing based on hex layout
        unit_size = (int(self._hex_layout.size * 1.5)) - 2
        js.document.documentElement.style.setProperty("--unit-width", f"{unit_size}px")
        js.document.documentElement.style.setProperty("--unit-height", f"{unit_size}px")

        # Zoom and pan state
        self._zoom_level = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._min_zoom = 0.5
        self._max_zoom = 3.0

        # Store background element for transforms
        self._bg_element = js.document.getElementById("map-bg")

        self._canvas_layer = CanvasLayer(
            canvas_element, self._hex_layout, self._hex_color, self._hex_stroke
        )
        self._svg_layer = SVGLayer(
            svg_element, self._hex_layout, self._hex_color, self._hex_stroke
        )
        self._unit_layer = UnitLayer(
            unit_element, self._hex_layout, self._hex_color, self._hex_stroke
        )

        self._dragHandler = MouseHandler(self._container, "mousemove", self._hex_layout, self)
        self._mouse_downHandler = MouseHandler(
            self._container, "mousedown", self._hex_layout, self
        )
        self._mouse_upHandler = MouseHandler(
            self._container, "mouseup", self._hex_layout, self
        )

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

        # Update CSS variables for unit sizing based on current hex layout
        unit_size = (int(self._hex_layout.size * 1.5)) - 2
        js.document.documentElement.style.setProperty("--unit-width", f"{unit_size}px")
        js.document.documentElement.style.setProperty("--unit-height", f"{unit_size}px")

        # Reapply current zoom and pan transforms
        self._apply_transform()

        logging.getLogger().info(
            f"Map refreshed: hex_size={self._hex_layout.size}, unit_size={unit_size}"
        )

    def _apply_transform(self) -> None:
        """
        Apply current zoom and pan transforms to all map layers.
        Uses scale first, then translate to avoid transform-origin issues.
        """
        # Apply scale around origin, then translate
        # This ensures (x,y) -> (x*zoom, y*zoom) -> (x*zoom + pan_x, y*zoom + pan_y)
        transform = f"translate({self._pan_x}px, {self._pan_y}px) scale({self._zoom_level})"
        
        # Apply to all layers
        if self._bg_element:
            self._bg_element.style.transform = transform
        self._canvas_layer.canvas.style.transform = transform
        self._svg_layer._svg.style.transform = transform
        self._unit_layer._svg.style.transform = transform

        logging.getLogger().debug(
            f"Applied transform: zoom={self._zoom_level:.2f}, pan=({self._pan_x:.1f}, {self._pan_y:.1f})"
        )

    def set_zoom(self, zoom_level: float, center_x: float = None, center_y: float = None) -> None:
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

        self._apply_transform()

    def adjust_zoom(self, delta: float, center_x: float = None, center_y: float = None) -> None:
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
        self._apply_transform()
        logging.getLogger().info("View reset to default")
