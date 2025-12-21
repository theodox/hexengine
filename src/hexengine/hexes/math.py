from .types import Hex, Cartesian
from typing import Iterable

# Constants for hex to cartesian conversion
SQRT_THREE = 3**0.5
THREE_HALF_POWER = SQRT_THREE / 2


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


def normalize(hex: Hex) -> Hex:
    i = (hex.i + 0.24999) / len(hex)
    j = (hex.j - 0.24999) / len(hex)
    k = -i - j
    return Hex(round(i), round(j), round(k))


def neighbors(hex: Hex) -> Iterable[Hex]:
    for hex_offset in _NEIGHBOR_OFFSETS:
        yield hex + hex_offset


def neighbor_hex(hex: Hex, direction: int) -> Hex:
    return hex + _NEIGHBOR_OFFSETS[direction % 6]


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
    """
    a_cart = Cartesian.from_hex(a)
    b_cart = Cartesian.from_hex(b)
    return float(a_cart.x) * float(b_cart.x) + float(a_cart.y) * float(b_cart.y)


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
    o_cart = Cartesian.from_hex(o)
    a_cart = Cartesian.from_hex(a)
    b_cart = Cartesian.from_hex(b)
    return (float(a_cart.x) - float(o_cart.x)) * (float(b_cart.y) - float(o_cart.y)) - (
        float(a_cart.y) - float(o_cart.y)
    ) * (float(b_cart.x) - float(o_cart.x))


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

    # Calculate magnitudes using Cartesian coordinates
    a_cart = Cartesian.from_hex(a)
    b_cart = Cartesian.from_hex(b)

    mag_a = sqrt(float(a_cart.x) * float(a_cart.x) + float(a_cart.y) * float(a_cart.y))
    mag_b = sqrt(float(b_cart.x) * float(b_cart.x) + float(b_cart.y) * float(b_cart.y))

    if mag_a == 0 or mag_b == 0:
        return 0.0  # Zero vector has no defined angle

    # Clamp to avoid floating point errors in acos
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

    cart = Cartesian.from_hex(hex_coord)
    return sqrt(float(cart.x) * float(cart.x) + float(cart.y) * float(cart.y))


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


def scale_cartesian_vector(vector: Cartesian, scalar: int) -> Cartesian:
    """
    Scale a Cartesian vector by a scalar value.

    Args:
        vector: Vector to scale
        scalar: Scalar multiplier

    Returns:
        Scaled vector
    """
    return vector * scalar
