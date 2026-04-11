from __future__ import annotations

import math
from collections.abc import Iterable
from math import cos, sin

from ..hexes.constants import (
    FLAT_TOP_AXIAL_TO_PLANE_X,
    FLAT_TOP_PLANE_TO_AXIAL_Q_SCALE,
    FLAT_TOP_PLANE_TO_AXIAL_R_COEFF_X,
    FLAT_TOP_PLANE_TO_AXIAL_R_COEFF_Y,
    HEX_SIDE_COUNT,
    PI_OVER_3,
    SQRT_THREE,
)
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
        x = self.size * (FLAT_TOP_AXIAL_TO_PLANE_X * hex.i) + self.origin_x
        y = self.size * (SQRT_THREE * (hex.j + hex.i / 2)) + self.origin_y
        return (x, y)

    def pixel_to_hex(self, x: float, y: float) -> Hex:
        x = (x - self.origin_x) / self.size
        y = (y - self.origin_y) / self.size
        q = FLAT_TOP_PLANE_TO_AXIAL_Q_SCALE * x
        r = (
            FLAT_TOP_PLANE_TO_AXIAL_R_COEFF_X * x
            + FLAT_TOP_PLANE_TO_AXIAL_R_COEFF_Y * y
        )
        return Hex(round(q), round(r), round(-q - r))

    def hex_corners(self, hex: Hex) -> list[tuple[float, float]]:
        center_x, center_y = self.hex_to_pixel(hex)
        corners = []
        for i in range(HEX_SIDE_COUNT):
            angle = PI_OVER_3 * i
            corner_x = center_x + self.size * cos(angle)
            corner_y = center_y + self.size * sin(angle)
            corners.append((corner_x, corner_y))
        return corners


def iter_map_grid_hexes(
    columns: int,
    rows: int,
    origin_i: int = 0,
    origin_j: int = 0,
) -> Iterable[Hex]:
    """Cube hexes for a rectangular map in axial ``(i, j)`` space."""
    for dj in range(rows):
        for di in range(columns):
            i = origin_i + di
            j = origin_j + dj
            yield Hex(i, j, -i - j)


def fit_hex_grid_canvas(
    hex_size: float,
    columns: int,
    rows: int,
    *,
    origin_i: int = 0,
    origin_j: int = 0,
    margin_pad: float = 0.0,
    stroke_pad: float = 2.0,
) -> tuple[HexLayout, int, int]:
    """
    Build a HexLayout and integer canvas size (width, height) that contain all
    hexes in the grid. Flat-top layout formula matches :class:`HexLayout`.
    """
    probe = HexLayout(hex_size, 0.0, 0.0)
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for h in iter_map_grid_hexes(columns, rows, origin_i, origin_j):
        for x, y in probe.hex_corners(h):
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)

    pad = float(stroke_pad) + float(margin_pad)
    ox = pad - min_x
    oy = pad - min_y
    layout = HexLayout(hex_size, ox, oy)

    max_x2 = max_y2 = -math.inf
    for h in iter_map_grid_hexes(columns, rows, origin_i, origin_j):
        for x, y in layout.hex_corners(h):
            max_x2 = max(max_x2, x)
            max_y2 = max(max_y2, y)

    cw = max(1, int(math.ceil(max_x2 + pad)))
    ch = max(1, int(math.ceil(max_y2 + pad)))
    return layout, cw, ch


def fit_hex_grid_canvas_for_hexes(
    hex_size: float,
    hexes: Iterable[Hex],
    *,
    margin_pad: float = 0.0,
    stroke_pad: float = 2.0,
) -> tuple[HexLayout, int, int]:
    """
    Like :func:`fit_hex_grid_canvas` but bounds the canvas to an explicit hex set
    (e.g. scenario terrain cells), omitting empty slots in an axis-aligned rectangle.
    """
    hex_list = list(hexes)
    if not hex_list:
        return HexLayout(hex_size, 0.0, 0.0), 1, 1
    probe = HexLayout(hex_size, 0.0, 0.0)
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for h in hex_list:
        for x, y in probe.hex_corners(h):
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)

    pad = float(stroke_pad) + float(margin_pad)
    ox = pad - min_x
    oy = pad - min_y
    layout = HexLayout(hex_size, ox, oy)

    max_x2 = max_y2 = -math.inf
    for h in hex_list:
        for x, y in layout.hex_corners(h):
            max_x2 = max(max_x2, x)
            max_y2 = max(max_y2, y)

    cw = max(1, int(math.ceil(max_x2 + pad)))
    ch = max(1, int(math.ceil(max_y2 + pad)))
    return layout, cw, ch
