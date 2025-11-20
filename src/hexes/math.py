from .types import Hex
from typing import Iterable


_NEIGHBOR_OFFSETS = []
for i in range(-1,2):
        for j in range(-1,2):
            k = -i - j
            if abs(k) <= 1 and not (i == 0 and j == 0 and k == 0):
                _NEIGHBOR_OFFSETS.append(Hex(i,j, k))



def cube_round(coords):
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