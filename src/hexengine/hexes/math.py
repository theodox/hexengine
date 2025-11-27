from .types import Hex, Cartesian, CartesianInt
from typing import Iterable
from collections import namedtuple

# Constants for hex to cartesian conversion
THREE_HALF_POWER = 3 ** 0.5 / 2


_NEIGHBOR_OFFSETS = []
for i in range(-1,2):
        for j in range(-1,2):
            k = -i - j
            if abs(k) <= 1 and not (i == 0 and j == 0 and k == 0):
                _NEIGHBOR_OFFSETS.append(Hex(i,j, k))



def cube_round(coords):
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


# Cartesian coordinate conversion functions
def hex_to_cartesian(hex_coord: Hex) -> Cartesian:
    """Convert hex coordinates to Cartesian coordinates."""
    x = hex_coord.i + 0.5 * hex_coord.j
    y = THREE_HALF_POWER * hex_coord.j
    return Cartesian(x, y)

def hex_to_cartesian_int(hex_coord: Hex) -> CartesianInt:
    """Convert hex coordinates to integer Cartesian coordinates."""
    x = int(round(hex_coord.i + 0.5 * hex_coord.j))
    y = int(round(THREE_HALF_POWER * hex_coord.j))
    return CartesianInt(x, y)

def cartesian_to_hex(cartesian: Cartesian) -> Hex:
    """Convert Cartesian coordinates back to hex coordinates."""
    # Reverse the hex_to_cartesian transformation
    # x = i + 0.5 * j  =>  i = x - 0.5 * j
    # y = (√3/2) * j   =>  j = y / (√3/2) = (2/√3) * y
    
    j = cartesian.y / THREE_HALF_POWER
    i = cartesian.x - 0.5 * j
    k = -i - j
    
    # Round to nearest valid hex coordinate
    return cube_round((i, j, k))

def cartesian_int_to_hex(cartesian: CartesianInt) -> Hex:
    """Convert integer Cartesian coordinates back to hex coordinates."""
    j = cartesian.y / THREE_HALF_POWER
    i = cartesian.x - 0.5 * j
    k = -i - j
    
    # Round to nearest valid hex coordinate
    return cube_round((i, j, k))    

# Vector operations using Cartesian conversion
def add_cartesian_vectors(hex1: Hex, hex2: Hex) -> Hex:
    """Add two hex vectors by converting to Cartesian, adding, and converting back."""
    cart1 = hex_to_cartesian_int(hex1)
    cart2 = hex_to_cartesian_int(hex2)
    
    result_cart = cart1 + cart2
    return cartesian_int_to_hex(result_cart)

def subtract_cartesian_vectors(hex1: Hex, hex2: Hex) -> Hex:
    """Subtract two hex vectors by converting to Cartesian, subtracting, and converting back."""
    cart1 = hex_to_cartesian_int(hex1)
    cart2 = hex_to_cartesian_int(hex2)
    
    result_cart = cart1 - cart2
    return cartesian_int_to_hex(result_cart)


def scale_cartesian_vector(hex_coord: Hex, scale: float) -> Hex:
    """Scale a hex vector by converting to Cartesian, scaling, and converting back."""
    cart = hex_to_cartesian(hex_coord)
    
    result_cart = Cartesian(cart.x * scale, cart.y * scale)
    return cartesian_to_hex(result_cart)


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
    a_cart = hex_to_cartesian(a)
    b_cart = hex_to_cartesian(b)
    return a_cart.x * b_cart.x + a_cart.y * b_cart.y


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
    o_cart = hex_to_cartesian(o)
    a_cart = hex_to_cartesian(a)
    b_cart = hex_to_cartesian(b)
    return (a_cart.x - o_cart.x) * (b_cart.y - o_cart.y) - \
           (a_cart.y - o_cart.y) * (b_cart.x - o_cart.x)


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
    a_cart = hex_to_cartesian(a)
    b_cart = hex_to_cartesian(b)
    
    mag_a = sqrt(a_cart.x * a_cart.x + a_cart.y * a_cart.y)
    mag_b = sqrt(b_cart.x * b_cart.x + b_cart.y * b_cart.y)
    
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
    cart = hex_to_cartesian(hex_coord)
    return sqrt(cart.x * cart.x + cart.y * cart.y)