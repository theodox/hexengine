from .math import (
    Cartesian,
    add_cartesian_vectors,
    cartesian_to_hex,
    cross_product,
    cube_round,
    distance,
    dot_product,
    hex_magnitude,
    hex_to_cartesian,
    lerp,
    line,
    neighbor_hex,
    neighbors,
    normalize,
    rotate_left,
    rotate_right,
    scale_cartesian_vector,
    subtract_cartesian_vectors,
)
from .shapes import (
    angle,
    convex_hull,
    convex_polygon,
    outer_boundary,
    path,
    polygon,
    radius,
    ring,
    wedge,
    wedge_fill,
)
from .types import Hex, HexRowCol

# Version info
__version__ = "0.1.0"

# Commonly used items available at package level
__all__ = [
    "Hex",
    "Cartesian",
    "HexRowCol",
    # Math functions
    "distance",
    "neighbors",
    "neighbor_hex",
    "line",
    "lerp",
    "rotate_left",
    "rotate_right",
    "cube_round",
    "normalize",
    "hex_to_cartesian",
    "cartesian_to_hex",
    "dot_product",
    "cross_product",
    "vector_angle",
    "hex_magnitude",
    "add_cartesian_vectors",
    "subtract_cartesian_vectors",
    "scale_cartesian_vector",
    # Shape functions
    "radius",
    "ring",
    "path",
    "wedge",
    "angle",
    "wedge_fill",
    "convex_hull",
    "outer_boundary",
    "polygon",
    "convex_polygon",
]