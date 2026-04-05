from __future__ import annotations

from math import cos, pi, sin, sqrt

from ..hexes.types import Hex


class HexLayout:
    """
    Converts between hex coordinates and pixel coordinates for flat-topped hexagons
    """

    """
    rect = event.target.getBoundingClientRect()
            x = event.clientX - rect.left
            y = event.clientY - rect.top
            sx = self._svg.width.baseVal.value / rect.width
            sy = self._svg.height.baseVal.value / rect.height
            return (x *sx, y * sy)
    """

    def __init__(
        self,
        size: float,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        margin: float = 0.0,
    ):
        self.size = size
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.margin = margin

    def hex_to_pixel(self, hex: Hex) -> tuple[float, float]:
        x = self.size * (3 / 2 * hex.i) + self.origin_x
        y = self.size * ((3**0.5) * (hex.j + hex.i / 2)) + self.origin_y
        return (x, y)

    def pixel_to_hex(self, x: float, y: float) -> Hex:
        x = (x - self.origin_x) / self.size
        y = (y - self.origin_y) / self.size
        q = 2.0 / 3 * x
        r = -1.0 / 3 * x + sqrt(3) / 3 * y
        return Hex(round(q), round(r), round(-q - r))

    def hex_corners(self, hex: Hex) -> list[tuple[float, float]]:
        center_x, center_y = self.hex_to_pixel(hex)
        corners = []
        for i in range(6):
            angle = 2 * pi * i / 6
            corner_x = center_x + self.size * cos(angle)
            corner_y = center_y + self.size * sin(angle)
            corners.append((corner_x, corner_y))
        return corners
