"""
Line-of-sight (LOS) helpers for hex grids.

This module is intentionally **state-agnostic**: callers supply a `blocks(hex) -> bool`
predicate describing what counts as LOS-blocking (terrain, units, smoke, etc.).

LOS rule supported:
- A ray may trace along the edge of a single blocking hex (grazing is allowed).
- A ray may *not* trace along the edge shared by *two* blocking hexes.

Implementation note:
We resolve "exact edge" ambiguity by testing two infinitesimally-offset rays on
opposite sides of the centerline. LOS is clear if either offset ray is clear.
"""

from __future__ import annotations

from collections.abc import Callable

from .constants import FLAT_TOP_AXIAL_TO_PLANE_X, FLAT_TOP_PLANE_TO_AXIAL_Q_SCALE, SQRT_THREE
from .math import cube_round, distance
from .types import Hex


def _hex_to_plane_xy(h: Hex) -> tuple[float, float]:
    # Same continuous flat-top embedding as `hexengine.hexes.math` uses internally.
    x = FLAT_TOP_AXIAL_TO_PLANE_X * h.i
    y = SQRT_THREE * (h.j + h.i * 0.5)
    return (x, y)


def _hex_from_plane_xy(x: float, y: float) -> Hex:
    # Continuous plane -> axial floats -> cube round.
    i = FLAT_TOP_PLANE_TO_AXIAL_Q_SCALE * x
    j = y / SQRT_THREE - i * 0.5
    k = -i - j
    return cube_round((i, j, k))


def _ray_hexes(a: Hex, b: Hex, *, nudge_sign: float) -> list[Hex]:
    """
    Discretize a straight ray between `a` and `b` into visited hexes.

    `nudge_sign` should be +1.0 or -1.0; it offsets the whole segment by a tiny
    perpendicular amount to choose a consistent side when the centerline rides
    exactly on a hex edge.
    """
    n = int(distance(a, b))
    if n <= 0:
        return [a]

    ax, ay = _hex_to_plane_xy(a)
    bx, by = _hex_to_plane_xy(b)
    dx, dy = (bx - ax), (by - ay)

    # Perpendicular unit vector in plane space.
    # If for any reason dx/dy are both 0, just avoid division.
    mag = (dx * dx + dy * dy) ** 0.5
    if mag <= 0.0:
        return [a]
    px, py = (-dy / mag), (dx / mag)

    # Tiny offset: just enough to pick a side deterministically.
    eps = 1e-6
    ox, oy = (px * eps * float(nudge_sign)), (py * eps * float(nudge_sign))

    out: list[Hex] = []
    last: Hex | None = None
    for step in range(n + 1):
        t = step / n
        x = ax + dx * t + ox
        y = ay + dy * t + oy
        h = _hex_from_plane_xy(x, y)
        if last is None or h != last:
            out.append(h)
            last = h
    return out


def has_line_of_sight(
    a: Hex,
    b: Hex,
    *,
    blocks: Callable[[Hex], bool],
) -> bool:
    """
    Return True if `a` has LOS to `b` under the caller-supplied `blocks` predicate.

    Endpoints `a` and `b` are *not* tested against `blocks` (only intermediate hexes).
    """
    if a == b:
        return True

    # If the ray grazes an edge, these two paths fall on opposite sides.
    paths = (
        _ray_hexes(a, b, nudge_sign=+1.0),
        _ray_hexes(a, b, nudge_sign=-1.0),
    )
    for path in paths:
        blocked = False
        for h in path[1:-1]:
            if blocks(h):
                blocked = True
                break
        if not blocked:
            return True
    return False


__all__ = ["has_line_of_sight"]

