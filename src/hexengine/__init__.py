"""
Hexes - A hexagonal grid game/application package.

This package provides both a hexagonal mathematics library (src.hexes)
and application components for building hex-based games and visualizations.
"""

from __future__ import annotations

from .hexes import *  # Import all the hex math library functions

# Application modules are available as submodules
# from . import engine, document, map, dev_console

__version__ = "0.1.3"


# Main entry point
def main() -> None:
    """Entry point for the application."""
    from . import __main__

    return __main__.main()


# Make this available for Pyodide
__all__ = [
    # Re-export from hexes library
    "Hex",
    "Cartesian",
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
    "scale_cartesian_vector",
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
    # Application entry point
    "main",
]
