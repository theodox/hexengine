from .types import Hex
from .math import line, neighbor_hex, distance, neighbors

from typing import Iterable, Sequence, Set, List
from math import cos, sin, atan2, pi

TWO_PI = 2 * pi
PI_OVER_3 = pi / 3.0
PI_OVER_6 = pi / 6.0


def path(steps: Sequence[Hex]) -> Iterable[Hex]:
    """
    Yields all hexes along a path defined by a sequence of hexes.
    """
    if len(steps) < 2:
        return
    for idx in range(len(steps) - 1):
        a = steps[idx]
        b = steps[idx + 1]
        for h in line(a, b):
            yield h


def radius(center: Hex, radius: int) -> Iterable[Hex]:
    """
    Yields all hexes within a given radius from the center hex.
    """
    for x in range(-radius, radius + 1):
        for y in range(max(-radius, -x - radius), min(radius, -x + radius) + 1):
            z = -x - y
            yield Hex(center.i + x, center.j + y, center.k + z)


def ring(center: Hex, rad_distance: int) -> Iterable[Hex]:
    """
    Yields all hexes exactly at a given radius from the center hex.
    """
    for r in radius(center, rad_distance):
        if distance(center, r) == rad_distance:
            yield r


def wedge(center: Hex, rad_distance: int, direction: int) -> Iterable[Hex]:
    for r in radius(center, rad_distance):
        dir_hex = neighbor_hex(center, direction)
        if distance(center, r) == rad_distance and distance(center, r + dir_hex) < rad_distance:
            yield r


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


def convex_hull(hexes: Iterable[Hex]) -> List[Hex]:
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
    
    # Convert to Cartesian coordinates for convex hull algorithm
    def hex_to_cartesian(hex_coord: Hex) -> tuple[float, float]:
        """Convert hex coordinates to Cartesian coordinates."""
        x = hex_coord.i + 0.5 * hex_coord.j
        y = (3**0.5 / 2) * hex_coord.j
        return (x, y)
    
    # Graham scan algorithm adapted for hex coordinates
    def cross_product(o: Hex, a: Hex, b: Hex) -> float:
        """Calculate cross product to determine turn direction."""
        o_cart = hex_to_cartesian(o)
        a_cart = hex_to_cartesian(a)
        b_cart = hex_to_cartesian(b)
        return (a_cart[0] - o_cart[0]) * (b_cart[1] - o_cart[1]) - \
               (a_cart[1] - o_cart[1]) * (b_cart[0] - o_cart[0])
    
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


def outer_boundary(hexes: Iterable[Hex]) -> Set[Hex]:
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
