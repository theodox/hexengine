from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .centerline import (
    LinearFeaturePath,
    consecutive_step_on_path,
    linear_feature_path_around_hexes,
    perimeter_hex_path,
    silhouette_edge,
    validate_linear_hex_path,
)
from .edges import (
    EdgeKey,
    direction_toward_neighbor,
    edge_between,
    edge_keys_along_hex_chain,
    edge_keys_for_shape_path,
    exterior_edge_keys_for_hexes,
    incident_edge_keys_for_hexes,
    incident_edge_keys_iter,
    internal_edge_keys_for_hexes,
    shared_edge_side_midpoint,
)
from .los import has_line_of_sight
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
    shift_axial_ij_cube_coords_to_origin,
    subtract_cartesian_vectors,
)
from .shapes import (
    HexLike,
    _as_hex,
    angle,
    angular_sector_hexes,
    convex_hull,
    convex_polygon,
    fill_convex_polygon,
    filled_wedge,
    hex_line_segment,
    outer_boundary,
    path,
    polygon,
    radius,
    ring,
    wedge,
    wedge_fill,
)
from .types import Hex, HexColRow
from .vertices import (
    VertexKey,
    shortest_edge_key_path_within_vertex_a_star,
    shortest_edge_key_path_within_vertex_bfs,
    vertex_key_pair_for_edge_key,
)

__version__: str
try:
    __version__ = version("hexes")
except PackageNotFoundError:
    __version__ = "0.1.3"

# Commonly used items available at package level
__all__ = [
    "Hex",
    "Cartesian",
    "HexColRow",
    "HexLike",
    "_as_hex",
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
    "shift_axial_ij_cube_coords_to_origin",
    "hex_to_cartesian",
    "cartesian_to_hex",
    "dot_product",
    "cross_product",
    "hex_magnitude",
    "add_cartesian_vectors",
    "subtract_cartesian_vectors",
    "scale_cartesian_vector",
    # Shape functions
    "radius",
    "ring",
    "path",
    "hex_line_segment",
    "wedge",
    "filled_wedge",
    "angle",
    "wedge_fill",
    "angular_sector_hexes",
    "convex_hull",
    "outer_boundary",
    "polygon",
    "convex_polygon",
    "fill_convex_polygon",
    # LOS
    "has_line_of_sight",
    # Map edges / centerlines
    "EdgeKey",
    "edge_between",
    "direction_toward_neighbor",
    "edge_keys_along_hex_chain",
    "edge_keys_for_shape_path",
    "exterior_edge_keys_for_hexes",
    "incident_edge_keys_for_hexes",
    "incident_edge_keys_iter",
    "internal_edge_keys_for_hexes",
    "shared_edge_side_midpoint",
    "VertexKey",
    "vertex_key_pair_for_edge_key",
    "shortest_edge_key_path_within_vertex_bfs",
    "shortest_edge_key_path_within_vertex_a_star",
    "LinearFeaturePath",
    "validate_linear_hex_path",
    "consecutive_step_on_path",
    "perimeter_hex_path",
    "silhouette_edge",
    "linear_feature_path_around_hexes",
]
