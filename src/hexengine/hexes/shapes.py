from collections.abc import Iterable, Sequence
from functools import singledispatch
from math import atan2, cos, pi, sin

from .math import cross_product, distance, line, neighbor_hex, neighbors
from .types import Cartesian, Hex

TWO_PI = 2 * pi
PI_OVER_3 = pi / 3.0
PI_OVER_6 = pi / 6.0
SQRT_THREE = 3**0.5


@singledispatch
def path(steps: Sequence[Hex]) -> Iterable[Hex]:
    """
    Yields all hexes along a path defined by a sequence of hexes.
    """
    if len(steps) < 2:
        return
    for idx in range(len(steps) - 1):
        a = steps[idx]
        b = steps[idx + 1]
        yield from line(a, b)


@path.register(Cartesian)
def _path(steps: Sequence[Cartesian]) -> Iterable[Hex]:
    """
    Yields all hexes along a path defined by a sequence of Cartesian coordinates.
    """
    if len(steps) < 2:
        return
    for idx in range(len(steps) - 1):
        a = Hex.from_cartesian(steps[idx])
        b = Hex.from_cartesian(steps[idx + 1])
        yield from line(a, b)


@singledispatch
def radius(center: Hex, radius: int) -> Iterable[Hex]:
    """
    Yields all hexes within a given radius from the center hex.
    """
    for x in range(-radius, radius + 1):
        for y in range(max(-radius, -x - radius), min(radius, -x + radius) + 1):
            z = -x - y
            yield Hex(center.i + x, center.j + y, center.k + z)


@radius.register(Cartesian)
def _radius(center: Cartesian, radius: int) -> Iterable[Hex]:
    """
    Yields all hexes within a given radius from the center Cartesian coordinate.
    """
    center_hex = Hex.from_cartesian(center)
    for x in range(-radius, radius + 1):
        for y in range(max(-radius, -x - radius), min(radius, -x + radius) + 1):
            z = -x - y
            yield Hex(center_hex.i + x, center_hex.j + y, center_hex.k + z)


@singledispatch
def ring(center: Hex, rad_distance: int) -> Iterable[Hex]:
    """
    Yields all hexes exactly at a given radius from the center hex.
    """
    for r in radius(center, rad_distance):
        if distance(center, r) == rad_distance:
            yield r


@ring.register(Cartesian)
def _ring(center: Cartesian, rad_distance: int) -> Iterable[Hex]:
    """
    Yields all hexes exactly at a given radius from the center Cartesian coordinate.
    """
    center_hex = Hex.from_cartesian(center)
    for r in radius(center_hex, rad_distance):
        if distance(center_hex, r) == rad_distance:
            yield r


def wedge(center: Hex, rad_distance: int, direction: int) -> Iterable[Hex]:
    """
    Yields all hexes in a 60 degree wedge from the center hex in the specified direction.
    """
    for r in radius(center, rad_distance):
        dir_hex = neighbor_hex(center, direction)
        if (
            distance(center, r) == rad_distance
            and distance(center, r + dir_hex) < rad_distance
        ):
            yield r


def rectangle_from_corners(corner1: Hex, corner2: Hex) -> Iterable[Hex]:
    """
    Yields all hexes within the rectangle defined by two corner hexes.
    The rectangle is axis-aligned in Cartesian coordinates.

    Note: Since multiple integer Cartesian coordinates can map to the same hex
    (because hex cells are larger than 1 unit), this function deduplicates results.
    """
    cc1 = Cartesian.from_hex(corner1)
    cc2 = Cartesian.from_hex(corner2)
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


def angle(start: Hex, end: Hex) -> float:
    delta = end - start
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
    center: Hex, rad_distance: int, start_angle: float, end_angle: float
) -> Iterable[Hex]:
    # 0.05 is 3 degrees of leeway to make sure we dont miss the 0 line
    for rad in radius(center, rad_distance):
        ang = angle(center, rad)
        if start_angle - 0.06 <= ang <= end_angle or rad == center:
            yield rad


def convex_hull(hexes: Iterable[Hex]) -> list[Hex]:
    """
    Find the convex hull of a set of hexes.

    Returns a list of hexes that form the convex hull boundary, ordered clockwise
    starting from the hex with the smallest i coordinate (leftmost).

    For hexagonal grids, this finds the hexes on the outer boundary that would
    form a convex shape if connected.
    """
    hex_set = set(hexes)
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


def outer_boundary(hexes: Iterable[Hex]) -> set[Hex]:
    """
    Find all hexes on the outer boundary of a set of hexes.

    Returns all hexes that have at least one neighbor not in the original set.
    This is different from convex hull as it includes concave boundaries.
    """
    hex_set = set(hexes)
    boundary = set()

    for hex_coord in hex_set:
        for neighbor in neighbors(hex_coord):
            if neighbor not in hex_set:
                boundary.add(hex_coord)
                break

    return boundary


def polygon(vertices: Sequence[Hex]) -> set[Hex]:
    """
    Fill a polygon defined by hex vertices using a scanline algorithm.

    Args:
        vertices: Sequence of hex coordinates defining the polygon boundary

    Returns:
        Set of all hexes inside and on the boundary of the polygon

    The algorithm:
    1. Creates the polygon boundary by connecting vertices with lines
    2. Uses a scanline approach to fill the interior
    3. For each potential row (i-coordinate), finds intersections and fills between them
    """
    if len(vertices) < 3:
        return set(vertices)

    # Create the polygon boundary
    boundary_hexes = set()
    for i in range(len(vertices)):
        start = vertices[i]
        end = vertices[(i + 1) % len(vertices)]
        boundary_line = list(line(start, end))
        boundary_hexes.update(boundary_line)

    # Find bounding box
    min_i = min(v.i for v in vertices)
    max_i = max(v.i for v in vertices)
    min_j = min(v.j for v in vertices)
    max_j = max(v.j for v in vertices)

    filled = set(boundary_hexes)  # Start with boundary

    # Use flood fill from interior points
    # Find a point that's definitely inside by using centroid
    centroid_i = sum(v.i for v in vertices) // len(vertices)
    centroid_j = sum(v.j for v in vertices) // len(vertices)
    centroid_k = -centroid_i - centroid_j
    start_point = Hex(centroid_i, centroid_j, centroid_k)

    # If centroid is not inside, try points near centroid
    candidates = [start_point]
    for offset in neighbors(start_point):
        candidates.append(offset)

    for candidate in candidates:
        if candidate not in boundary_hexes and _point_in_polygon(candidate, vertices):
            _flood_fill(candidate, boundary_hexes, filled, min_i, max_i, min_j, max_j)
            break

    return filled


def _point_in_polygon(point: Hex, vertices: Sequence[Hex]) -> bool:
    """
    Test if a point is inside a polygon using ray casting algorithm.
    Adapted for hexagonal coordinates by converting to Cartesian.
    """

    def hex_to_cartesian(hex_coord: Hex) -> tuple[float, float]:
        x = 1.5 * hex_coord.i
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


def convex_polygon(vertices: Sequence[Hex]) -> set[Hex]:
    """
    Fill a convex polygon more efficiently using scanline algorithm.

    Args:
        vertices: Sequence of hex coordinates defining the convex polygon

    Returns:
        Set of all hexes inside and on the boundary of the polygon

    This is more efficient than the general fill_polygon for convex shapes.
    """
    if len(vertices) < 3:
        return set(vertices)

    # Create boundary
    boundary_hexes = set()
    for i in range(len(vertices)):
        start = vertices[i]
        end = vertices[(i + 1) % len(vertices)]
        boundary_line = list(line(start, end))
        boundary_hexes.update(boundary_line)

    # For convex polygons, we can use a simpler approach
    # Find all hexes in the bounding box and test if they're inside
    min_i = min(v.i for v in vertices)
    max_i = max(v.i for v in vertices)
    min_j = min(v.j for v in vertices)
    max_j = max(v.j for v in vertices)

    filled = set(boundary_hexes)

    for i in range(min_i, max_i + 1):
        for j in range(min_j, max_j + 1):
            k = -i - j
            candidate = Hex(i, j, k)

            if candidate not in boundary_hexes and _point_in_polygon(
                candidate, vertices
            ):
                filled.add(candidate)

    return filled


fill_convex_polygon = convex_polygon
