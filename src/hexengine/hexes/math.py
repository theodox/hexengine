from __future__ import annotations

from collections.abc import Iterable

from .constants import (
    FLAT_TOP_AXIAL_TO_PLANE_X,
    FLAT_TOP_PLANE_TO_AXIAL_Q_SCALE,
    HEX_SIDE_COUNT,
    NORMALIZE_HEX_EPSILON,
    SQRT_THREE,
)
from .types import Cartesian, Hex


def _hex_to_axial_plane_xy(h: Hex) -> tuple[float, float]:
    """Continuous flat-top plane coords (matches polygon ray-cast in shapes)."""
    x = FLAT_TOP_AXIAL_TO_PLANE_X * h.i
    y = SQRT_THREE * (h.j + h.i * 0.5)
    return (x, y)


_NEIGHBOR_OFFSETS = []
for i in range(-1, 2):
    for j in range(-1, 2):
        k = -i - j
        if abs(k) <= 1 and not (i == 0 and j == 0 and k == 0):
            _NEIGHBOR_OFFSETS.append(Hex(i, j, k))


def cube_round(coords: tuple[float, float, float]) -> Hex:
    """
    Rounds fractional cube coordinates to the nearest hex.
    """
    q = round(coords[0])
    r = round(coords[1])
    s = round(coords[2])

    q_diff = abs(q - coords[0])
    r_diff = abs(r - coords[1])
    s_diff = abs(s - coords[2])

    if q_diff > r_diff and q_diff > s_diff:
        q = -r - s
    elif r_diff > s_diff:
        r = -q - s
    else:
        s = -q - r
    return Hex(q, r, s)


def shift_axial_ij_cube_coords_to_origin(
    coords: Iterable[tuple[int, int, int]],
) -> list[tuple[int, int, int]]:
    """
    Shift ``(i, j)`` so the set's minimum ``i`` and ``j`` are 0.

    ``k`` is recomputed as ``-i - j`` after the shift (scenario-style bounding box),
    ignoring any previous ``k`` in the input.
    """
    lst = list(coords)
    if not lst:
        return []
    min_i = min(t[0] for t in lst)
    min_j = min(t[1] for t in lst)
    return [
        (i - min_i, j - min_j, -(i - min_i) - (j - min_j)) for i, j, _k in lst
    ]


def normalize(hex: Hex) -> Hex:
    i = (hex.i + NORMALIZE_HEX_EPSILON) / len(hex)
    j = (hex.j - NORMALIZE_HEX_EPSILON) / len(hex)
    k = -i - j
    return Hex(round(i), round(j), round(k))


def neighbors(hex: Hex) -> Iterable[Hex]:
    for hex_offset in _NEIGHBOR_OFFSETS:
        yield hex + hex_offset


def neighbor_hex(hex: Hex, direction: int) -> Hex:
    return hex + _NEIGHBOR_OFFSETS[direction % HEX_SIDE_COUNT]


def distance(a: Hex, b: Hex) -> int:
    return len(b - a)


def lerp(a: Hex, b: Hex, t: float) -> Hex:
    i = a.i + (b.i - a.i) * t
    j = a.j + (b.j - a.j) * t
    k = a.k + (b.k - a.k) * t
    return cube_round((i, j, k))


def line(a: Hex, b: Hex) -> Iterable[Hex]:
    N = distance(a, b)

    for i in range(N + 1):
        t = i / max(N, 1)
        next_hex = lerp(a, b, t)
        yield next_hex


def rotate_left(hex: Hex) -> Hex:
    return Hex(-hex.k, -hex.i, -hex.j)


def rotate_right(hex: Hex) -> Hex:
    return Hex(-hex.j, -hex.k, -hex.i)


def dot_product(a: Hex, b: Hex) -> float:
    """
    Calculate dot product of two hex vectors.

    Args:
        a: First hex vector
        b: Second hex vector

    Returns:
        Dot product value (unitless scalar)

    The dot product represents:
    - Positive: Vectors point in similar directions
    - Zero: Vectors are perpendicular
    - Negative: Vectors point in opposite directions
    - Magnitude: Related to the cosine of angle between vectors

    Uses continuous flat-top plane coordinates (same as polygon fills in shapes),
    not rounded integer pixel coords, so cube-collinear vectors stay collinear.
    """
    ax, ay = _hex_to_axial_plane_xy(a)
    bx, by = _hex_to_axial_plane_xy(b)
    return ax * bx + ay * by


def cross_product(o: Hex, a: Hex, b: Hex) -> float:
    """
    Calculate cross product to determine turn direction.
    The sign will indicate whether we have a left or right turn,
    the magnitude represents twice the area of the triangle formed by the points.

    Returns:
        Cross product value representing twice the signed area of triangle o-a-b
        - Positive: Counter-clockwise turn (left turn)
        - Negative: Clockwise turn (right turn)
        - Zero: Collinear points
    """
    oxy = _hex_to_axial_plane_xy(o)
    axy = _hex_to_axial_plane_xy(a)
    bxy = _hex_to_axial_plane_xy(b)
    return (axy[0] - oxy[0]) * (bxy[1] - oxy[1]) - (axy[1] - oxy[1]) * (bxy[0] - oxy[0])


def vector_angle(a: Hex, b: Hex) -> float:
    """
    Calculate the angle between two hex vectors using dot product.

    Args:
        a: First hex vector
        b: Second hex vector

    Returns:
        Angle in radians between the vectors (0 to π)
    """
    from math import acos, sqrt

    dot = dot_product(a, b)
    mag_a = sqrt(dot_product(a, a))
    mag_b = sqrt(dot_product(b, b))

    if mag_a == 0 or mag_b == 0:
        return 0.0  # Zero vector has no defined angle

    cos_angle = max(-1.0, min(1.0, dot / (mag_a * mag_b)))
    return acos(cos_angle)


def hex_magnitude(hex_coord: Hex) -> float:
    """
    Calculate the magnitude (length) of a hex vector in Cartesian space.

    Args:
        hex_coord: Hex vector

    Returns:
        Magnitude as a float (unitless)
    """
    from math import sqrt

    x, y = _hex_to_axial_plane_xy(hex_coord)
    return sqrt(x * x + y * y)


def hex_to_cartesian(hex_coord: Hex) -> Cartesian:
    """
    Convert hex coordinates to Cartesian coordinates (flat-top orientation).

    Args:
        hex_coord: Hex coordinate to convert

    Returns:
        Cartesian coordinate
    """
    return Cartesian.from_hex(hex_coord)


def cartesian_to_hex(cartesian: Cartesian) -> Hex:
    """
    Convert Cartesian coordinates to hex coordinates (flat-top orientation).

    Args:
        cartesian: Cartesian coordinate to convert

    Returns:
        Hex coordinate
    """
    return Hex.from_cartesian(cartesian)


def add_cartesian_vectors(a: Cartesian, b: Cartesian) -> Cartesian:
    """
    Add two Cartesian vectors.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Sum of the two vectors
    """
    return a + b


def subtract_cartesian_vectors(a: Cartesian, b: Cartesian) -> Cartesian:
    """
    Subtract one Cartesian vector from another.

    Args:
        a: Vector to subtract from
        b: Vector to subtract

    Returns:
        Difference of the two vectors (a - b)
    """
    return a - b


def scale_cartesian_vector(vector: Hex | Cartesian, scalar: float) -> Hex:
    """
    Scale a vector in continuous flat-top plane space, then round to the nearest hex.

    Accepts a Hex or integer Cartesian lattice vector and a float scalar.
    """
    if isinstance(vector, Hex):
        x, y = _hex_to_axial_plane_xy(vector)
    else:
        x, y = float(vector.x), float(vector.y)
    x *= scalar
    y *= scalar
    i = FLAT_TOP_PLANE_TO_AXIAL_Q_SCALE * x
    j = y / SQRT_THREE - i * 0.5
    k = -i - j
    return cube_round((i, j, k))
