from .types import Hex
from .math import line, neighbor_hex, distance

from typing import Iterable, Sequence
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


def ring(center: Hex, radius: int) -> Iterable[Hex]:
    """
    Yields all hexes exactly at a given radius from the center hex.
    """
    for r in radius(center, radius):
        if distance(center, r) == radius:
            yield r


def wedge(center: Hex, radius: int, direction: int) -> Iterable[Hex]:
    for r in radius(center, radius):
        dir_hex = neighbor_hex(center, direction)
        if distance(center, r) == radius and distance(center, r + dir_hex) < radius:
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
    center: Hex, radius: int, start_angle: float, end_angle: float
) -> Iterable[Hex]:
    # 0.05 is 3 degrees of leeway to make sure we dont miss the 0 line
    for rad in radius(center, radius):
        ang = angle(center, rad)
        if start_angle - 0.06 <= ang <= end_angle or rad == center:
            yield rad
