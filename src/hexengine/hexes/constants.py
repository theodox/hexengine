"""
Shared numeric constants for hex grid math.

Kept free of imports from other ``hexes`` modules so ``types`` and ``math``
can both use these without circular dependencies.
"""

from __future__ import annotations

from math import pi

# --- Flat-top axial ↔ plane (continuous), unit hex radius in plane space ---
SQRT_THREE = 3**0.5
# x_plane = FLAT_TOP_AXIAL_TO_PLANE_X * i  (same as 3/2)
FLAT_TOP_AXIAL_TO_PLANE_X = 1.5
# Inverse of the layout matrix (see HexLayout.pixel_to_hex, scale_cartesian_vector).
FLAT_TOP_PLANE_TO_AXIAL_Q_SCALE = 2.0 / 3.0
FLAT_TOP_PLANE_TO_AXIAL_R_COEFF_X = -1.0 / 3.0
FLAT_TOP_PLANE_TO_AXIAL_R_COEFF_Y = SQRT_THREE / 3.0

# --- Angles (flat-top hex geometry, cube-axis projections) ---
TWO_PI = 2 * pi
PI_OVER_3 = pi / 3.0
PI_OVER_6 = pi / 6.0

# --- Topology ---
HEX_SIDE_COUNT = 6

# --- normalize() fractional hex coords ---
NORMALIZE_HEX_EPSILON = 0.24999
