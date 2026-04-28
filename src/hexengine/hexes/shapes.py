from __future__ import annotations

from collections.abc import Iterable, Sequence
from math import atan2, cos, isclose, pi, sin
from typing import TypeAlias

from .constants import (
    FLAT_TOP_AXIAL_TO_PLANE_X,
    PI_OVER_3,
    PI_OVER_6,
    SQRT_THREE,
    TWO_PI,
)
from .math import cross_product, distance, line, neighbor_hex, neighbors
from .types import Cartesian, Hex, HexColRow

HexLike: TypeAlias = Hex | Cartesian | HexColRow


def _as_hex(p: HexLike) -> Hex:
    """Normalize a board cell from cube/axial, odd-q offset, or plane integer coords."""
    if isinstance(p, Hex):
        return p
    if isinstance(p, HexColRow):
        return p.to_hex()
    if isinstance(p, Cartesian):
        return Hex.from_cartesian(p)
    raise TypeError(
        f"expected Hex, HexColRow, or Cartesian for a cell argument; got {type(p).__name__}"
    )


def _path_polyline_hexes(hex_steps: Sequence[Hex]) -> Iterable[Hex]:
    if len(hex_steps) < 2:
        return
    for idx in range(len(hex_steps) - 1):
        yield from line(hex_steps[idx], hex_steps[idx + 1])


def path(steps: Sequence[HexLike]) -> Iterable[Hex]:
    """
    Yields all hexes along a path defined by a sequence of waypoints.

    Each waypoint may be Hex, HexColRow, or Cartesian (normalized via _as_hex); types may
    be mixed within one path.
    """
    if len(steps) < 2:
        return
    yield from _path_polyline_hexes(tuple(_as_hex(p) for p in steps))


def radius(center: HexLike, rad_distance: int) -> Iterable[Hex]:
    """
    Yields all hexes within a given cube distance (rad_distance) from center.

    center may be Hex, HexColRow, or Cartesian.
    """
    c = _as_hex(center)
    for x in range(-rad_distance, rad_distance + 1):
        for y in range(
            max(-rad_distance, -x - rad_distance),
            min(rad_distance, -x + rad_distance) + 1,
        ):
            z = -x - y
            yield Hex(c.i + x, c.j + y, c.k + z)


def ring(center: HexLike, rad_distance: int) -> Iterable[Hex]:
    """
    Yields all hexes exactly at a given radius from the center cell.

    center may be Hex, HexColRow, or Cartesian.
    """
    c = _as_hex(center)
    for r in radius(c, rad_distance):
        if distance(c, r) == rad_distance:
            yield r


def wedge(center: HexLike, rad_distance: int, direction: int) -> Iterable[Hex]:
    """
    Yields all hexes in a 60 degree wedge from the center hex in the specified direction.
    """
    c = _as_hex(center)
    for r in radius(c, rad_distance):
        dir_hex = neighbor_hex(c, direction)
        if (
            distance(c, r) == rad_distance
            and distance(c, r + dir_hex) < rad_distance
        ):
            yield r


def hex_line_segment(a: HexLike, b: HexLike) -> Iterable[Hex]:
    """
    Straight-line hex cells between a and b (inclusive).

    Same cells as path on a two-step polyline (a, b); uses hexes.math.line between steps.
    """
    return path((a, b))


def filled_wedge(center: HexLike, max_distance: int, direction: int) -> Iterable[Hex]:
    """
    Discrete 60° cone: center plus every wedge ring from 1 through max_distance.

    This matches the classic hex-side cone used with neighbor_hex(..., direction).
    """
    c = _as_hex(center)
    yield c
    md = int(max_distance)
    for r in range(1, md + 1):
        yield from wedge(c, r, int(direction))


def angular_sector_hexes(
    center: HexLike,
    max_distance: int,
    *,
    direction: int,
    half_angle: float,
) -> Iterable[Hex]:
    """
    Hexes inside a cone from center out to cube distance max_distance.

    When half_angle is approximately PI_OVER_6, uses filled_wedge (stacked wedge rings)
    for a discrete 60° sector. Otherwise uses wedge_fill in the angle convention of angle,
    centered on the ray toward neighbor_hex(center, direction).
    """
    md = int(max_distance)
    if md < 0:
        return

    c = _as_hex(center)
    if isclose(float(half_angle), float(PI_OVER_6), rel_tol=0.0, abs_tol=1e-9):
        yield from filled_wedge(c, md, direction)
        return

    center_dir_hex = neighbor_hex(c, int(direction))
    center_ang = angle(c, center_dir_hex)
    start = center_ang - float(half_angle)
    end = center_ang + float(half_angle)
    for h in wedge_fill(c, md, start, end):
        if distance(c, h) > md:
            continue
        yield h


def rectangle_from_corners(corner1: HexLike, corner2: HexLike) -> Iterable[Hex]:
    """
    Yields all hexes within the rectangle defined by two corner hexes.
    The rectangle is axis-aligned in Cartesian coordinates.

    Note: Since multiple integer Cartesian coordinates can map to the same hex
    (because hex cells are larger than 1 unit), this function deduplicates results.
    """
    h1 = _as_hex(corner1)
    h2 = _as_hex(corner2)
    cc1 = Cartesian.from_hex(h1)
    cc2 = Cartesian.from_hex(h2)
    min_x = min(cc1.x, cc2.x)
    max_x = max(cc1.x, cc2.x)
    min_y = min(cc1.y, cc2.y)
    max_y = max(cc1.y, cc2.y)

    seen = set()  # we can't guarantee uniqueness otherwise
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            h = Hex.from_cartesian(Cartesian(x, y))
            if h not in seen:
                seen.add(h)
                yield h


def angle(start: HexLike, end: HexLike) -> float:
    a = _as_hex(start)
    b = _as_hex(end)
    delta = b - a
    angle = PI_OVER_6  # 30 degrees for flat-topped hexes
    x = (
        delta.i * cos(angle)
        + delta.j * cos(angle + 2 * PI_OVER_3)
        + delta.k * cos(angle + 4 * PI_OVER_3)
    )
    y = (
        delta.i * sin(angle)
        + delta.j * sin(angle + 2 * PI_OVER_3)
        + delta.k * sin(angle + 4 * PI_OVER_3)
    )
    return (PI_OVER_3 + atan2(y, x) + TWO_PI) % TWO_PI


def wedge_fill(
    center: HexLike, rad_distance: int, start_angle: float, end_angle: float
) -> Iterable[Hex]:
    c = _as_hex(center)
    # 0.05 is 3 degrees of leeway to make sure we dont miss the 0 line
    for rad in radius(c, rad_distance):
        ang = angle(c, rad)
        if start_angle - 0.06 <= ang <= end_angle or rad == c:
            yield rad


def convex_hull(hexes: Iterable[HexLike]) -> list[Hex]:
    """
    Find the convex hull of a set of hexes.

    Returns a list of hexes that form the convex hull boundary, ordered clockwise
    starting from the hex with the smallest i coordinate (leftmost).

    For hexagonal grids, this finds the hexes on the outer boundary that would
    form a convex shape if connected.
    """
    hex_set = {_as_hex(h) for h in hexes}
    if len(hex_set) == 0:
        return []
    if len(hex_set) == 1:
        return list(hex_set)

    # Find boundary hexes - hexes that have at least one neighbor not in the set
    boundary_hexes = set()
    for hex_coord in hex_set:
        for neighbor in neighbors(hex_coord):
            if neighbor not in hex_set:
                boundary_hexes.add(hex_coord)
                break

    if len(boundary_hexes) <= 2:
        return sorted(boundary_hexes, key=lambda h: (h.i, h.j, h.k))

    # Find the starting point (leftmost, then bottommost)
    boundary_list = list(boundary_hexes)
    start = min(boundary_list, key=lambda h: (h.i, h.j))

    # Sort points by polar angle with respect to start point
    def polar_angle(hex_coord: Hex) -> float:
        if hex_coord == start:
            return -pi  # Ensure start point comes first
        return angle(start, hex_coord)

    sorted_points = sorted(boundary_list, key=polar_angle)

    # Build convex hull using Graham scan
    hull = []

    for point in sorted_points:
        # Remove points that create right turns
        while len(hull) >= 2 and cross_product(hull[-2], hull[-1], point) <= 0:
            hull.pop()
        hull.append(point)

    return hull


def outer_boundary(hexes: Iterable[HexLike]) -> set[Hex]:
    """
    Find all hexes on the outer boundary of a set of hexes.

    Returns all hexes that have at least one neighbor not in the original set.
    This is different from convex hull as it includes concave boundaries.
    """
    hex_set = {_as_hex(h) for h in hexes}
    boundary = set()

    for hex_coord in hex_set:
        for neighbor in neighbors(hex_coord):
            if neighbor not in hex_set:
                boundary.add(hex_coord)
                break

    return boundary


def polygon(vertices: Sequence[HexLike]) -> set[Hex]:
    """
    Fill a polygon defined by hex vertices using a scanline algorithm.

    vertices: sequence of cell coordinates (Hex, HexColRow, or Cartesian) defining the
    boundary. Returns the set of all hexes inside and on the boundary.

    Steps: build the boundary by connecting consecutive vertices with lines; scan/flood
    to fill the interior (i-coordinate bands and flood fill from a candidate inside point).
    """
    verts = tuple(_as_hex(v) for v in vertices)
    if len(verts) < 3:
        return set(verts)

    # Create the polygon boundary
    boundary_hexes = set()
    for i in range(len(verts)):
        start = verts[i]
        end = verts[(i + 1) % len(verts)]
        boundary_line = list(line(start, end))
        boundary_hexes.update(boundary_line)

    # Find bounding box
    min_i = min(v.i for v in verts)
    max_i = max(v.i for v in verts)
    min_j = min(v.j for v in verts)
    max_j = max(v.j for v in verts)

    filled = set(boundary_hexes)  # Start with boundary

    # Use flood fill from interior points
    # Find a point that's definitely inside by using centroid
    centroid_i = sum(v.i for v in verts) // len(verts)
    centroid_j = sum(v.j for v in verts) // len(verts)
    centroid_k = -centroid_i - centroid_j
    start_point = Hex(centroid_i, centroid_j, centroid_k)

    # If centroid is not inside, try points near centroid
    candidates = [start_point]
    for offset in neighbors(start_point):
        candidates.append(offset)

    for candidate in candidates:
        if candidate not in boundary_hexes and _point_in_polygon(candidate, verts):
            _flood_fill(candidate, boundary_hexes, filled, min_i, max_i, min_j, max_j)
            break

    return filled


def _point_in_polygon(point: Hex, vertices: Sequence[Hex]) -> bool:
    """
    Test if a point is inside a polygon using ray casting algorithm.
    Adapted for hexagonal coordinates by converting to Cartesian.
    """

    def hex_to_cartesian(hex_coord: Hex) -> tuple[float, float]:
        x = FLAT_TOP_AXIAL_TO_PLANE_X * hex_coord.i
        y = SQRT_THREE * (hex_coord.j + hex_coord.i * 0.5)
        return (x, y)

    px, py = hex_to_cartesian(point)
    n = len(vertices)
    inside = False

    j = n - 1
    for i in range(n):
        xi, yi = hex_to_cartesian(vertices[i])
        xj, yj = hex_to_cartesian(vertices[j])

        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i

    return inside


def _flood_fill(
    start: Hex,
    boundary: set[Hex],
    filled: set[Hex],
    min_i: int,
    max_i: int,
    min_j: int,
    max_j: int,
) -> None:
    """
    Flood fill algorithm to fill interior of polygon.
    """
    stack = [start]

    while stack:
        current = stack.pop()

        if (
            current in filled
            or current in boundary
            or current.i < min_i - 2
            or current.i > max_i + 2
            or current.j < min_j - 2
            or current.j > max_j + 2
        ):
            continue

        filled.add(current)

        # Add neighbors to stack
        for neighbor in neighbors(current):
            if neighbor not in filled and neighbor not in boundary:
                stack.append(neighbor)


def convex_polygon(vertices: Sequence[HexLike]) -> set[Hex]:
    """
    Fill a convex polygon more efficiently using a bounding-box scan.

    vertices: sequence of cell coordinates (Hex, HexColRow, or Cartesian) defining the
    convex boundary. Returns the set of all hexes inside and on the boundary. Faster than
    the general polygon fill for convex inputs.
    """
    verts = tuple(_as_hex(v) for v in vertices)
    if len(verts) < 3:
        return set(verts)

    # Create boundary
    boundary_hexes = set()
    for i in range(len(verts)):
        start = verts[i]
        end = verts[(i + 1) % len(verts)]
        boundary_line = list(line(start, end))
        boundary_hexes.update(boundary_line)

    # For convex polygons, we can use a simpler approach
    # Find all hexes in the bounding box and test if they're inside
    min_i = min(v.i for v in verts)
    max_i = max(v.i for v in verts)
    min_j = min(v.j for v in verts)
    max_j = max(v.j for v in verts)

    filled = set(boundary_hexes)

    for i in range(min_i, max_i + 1):
        for j in range(min_j, max_j + 1):
            k = -i - j
            candidate = Hex(i, j, k)

            if candidate not in boundary_hexes and _point_in_polygon(
                candidate, verts
            ):
                filled.add(candidate)

    return filled


fill_convex_polygon = convex_polygon
