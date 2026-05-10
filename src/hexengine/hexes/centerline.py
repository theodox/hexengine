"""
Centerline map features: validated paths of consecutive neighbor hexes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .math import distance, neighbors
from .shapes import HexLike, _as_hex, outer_boundary
from .types import Hex


def _hex_key(h: Hex) -> tuple[int, int, int]:
    return (h.i, h.j, h.k)


def _common_neighbors_of_edge(a: Hex, b: Hex) -> frozenset[Hex]:
    if distance(a, b) != 1:
        return frozenset()
    nb = frozenset(neighbors(b))
    return frozenset(x for x in neighbors(a) if x in nb)


def silhouette_edge(a: Hex, b: Hex, region: frozenset[Hex]) -> bool:
    """
    True if a and b are in region, adjacent, and the center-to-center step lies on the
    outside outline of the union (not an interior diagonal of a filled 2x2 rhombus).

    Two adjacent region hexes share two common neighbor cells. If both are in region,
    the step is interior. If neither is, the step runs along a thin exposed face (e.g.
    a dimer). If exactly one common c is in region, the step is interior when the
    parallelogram fourth corner b + c - a (cube) is also in region (complete 2x2 block).
    """
    if a not in region or b not in region or distance(a, b) != 1:
        return False
    commons = _common_neighbors_of_edge(a, b)
    inside = [h for h in commons if h in region]
    if len(inside) == 2:
        return False
    if len(inside) == 0:
        return True
    c = inside[0]
    fourth = Hex(b.i + c.i - a.i, b.j + c.j - a.j, b.k + c.k - a.k)
    return fourth not in region


def _boundary_silhouette_adjacency(
    region: frozenset[Hex], bset: frozenset[Hex]
) -> dict[Hex, list[Hex]]:
    adj: dict[Hex, list[Hex]] = defaultdict(list)
    seen: set[frozenset[Hex]] = set()
    for h in bset:
        for n in neighbors(h):
            if n not in bset:
                continue
            if not silhouette_edge(h, n, region):
                continue
            key = frozenset((h, n))
            if key in seen:
                continue
            seen.add(key)
            adj[h].append(n)
            adj[n].append(h)
    return {k: sorted(v, key=_hex_key) for k, v in adj.items()}


def perimeter_hex_path(region: frozenset[Hex]) -> tuple[Hex, ...]:
    """
    Ordered hex centers tracing the outside outline of a finite hex set.

    Uses silhouette edges between outer-boundary cells (see silhouette_edge). Simply
    connected regions yield one closed loop (last hex is adjacent to the first; repeat
    the first hex at the end so every consecutive pair is a neighbor move). Regions whose
    silhouette graph is an open chain (e.g. two hexes) return that chain without repeating
    the start.

    Raises ValueError if the region is empty, has fewer than two hexes on the outer
    boundary, or the silhouette graph is not a single cycle or simple path.
    """
    if len(region) < 2:
        raise ValueError("region must contain at least two hexes")
    bset = frozenset(outer_boundary(region))
    if len(bset) < 2:
        raise ValueError("outer boundary has fewer than two hexes")
    adj = _boundary_silhouette_adjacency(region, bset)
    for h in bset:
        adj.setdefault(h, [])
    degrees = {h: len(adj[h]) for h in bset}
    deg_counts = defaultdict(int)
    for d in degrees.values():
        deg_counts[d] += 1

    if all(d == 2 for d in degrees.values()):
        start = min(bset, key=_hex_key)
        return _walk_closed_perimeter(start, adj)
    if deg_counts[1] == 2 and all(d in (1, 2) for d in degrees.values()):
        ends = [h for h, d in degrees.items() if d == 1]
        start = min(ends, key=_hex_key)
        return tuple(_walk_open_perimeter(start, adj))
    raise ValueError(
        "perimeter is not a single loop or path (holes, thick junctions, or disjoint outline)"
    )


def _walk_closed_perimeter(start: Hex, adj: Mapping[Hex, list[Hex]]) -> tuple[Hex, ...]:
    path: list[Hex] = [start]
    prev: Hex | None = None
    current = start
    while True:
        nbrs = [n for n in adj[current] if n != prev]
        if not nbrs:
            raise ValueError("broken perimeter walk")
        if len(nbrs) == 1:
            nxt = nbrs[0]
        elif prev is None:
            nxt = min(nbrs, key=_hex_key)
        else:
            nxt_list = [n for n in nbrs if n != prev]
            if len(nxt_list) != 1:
                raise ValueError("ambiguous turn on perimeter")
            nxt = nxt_list[0]
        if nxt == start:
            return tuple(path + [start])
        path.append(nxt)
        prev, current = current, nxt
        if len(path) > len(adj) + 2:
            raise ValueError("perimeter walk failed to close")


def _walk_open_perimeter(start: Hex, adj: Mapping[Hex, list[Hex]]) -> list[Hex]:
    path: list[Hex] = [start]
    prev: Hex | None = None
    current = start
    while True:
        nbrs = [n for n in adj[current] if n != prev]
        if not nbrs:
            return path
        if len(nbrs) != 1:
            raise ValueError("unexpected branch in open perimeter")
        nxt = nbrs[0]
        path.append(nxt)
        prev, current = current, nxt


def linear_feature_path_around_hexes(hexes: Iterable[HexLike]) -> LinearFeaturePath:
    """
    Build a validated linear (centerline) path along the outside perimeter of the given
    hex cells. Cells may be Hex, HexColRow, or Cartesian (mixed allowed).
    """
    region = frozenset(_as_hex(h) for h in hexes)
    return validate_linear_hex_path(perimeter_hex_path(region))


@dataclass(frozen=True)
class LinearFeaturePath:
    """Ordered hex spine; each consecutive pair must be cube-adjacent."""

    hexes: tuple[Hex, ...]

    def __post_init__(self) -> None:
        h = self.hexes
        if len(h) < 2:
            raise ValueError("linear feature path requires at least two hexes")
        for i in range(len(h) - 1):
            if distance(h[i], h[i + 1]) != 1:
                raise ValueError(
                    f"path step {i}→{i + 1} is not a neighbor move: {h[i]!r} to {h[i + 1]!r}"
                )


def validate_linear_hex_path(hexes: tuple[Hex, ...]) -> LinearFeaturePath:
    """Return a validated path wrapper (raises ValueError if the chain is invalid)."""
    return LinearFeaturePath(hexes)


def consecutive_step_on_path(path: tuple[Hex, ...], a: Hex, b: Hex) -> bool:
    """True if (a, b) appears as consecutive hexes along the ordered path (either direction)."""
    if len(path) < 2:
        return False
    for i in range(len(path) - 1):
        if path[i] == a and path[i + 1] == b:
            return True
        if path[i] == b and path[i + 1] == a:
            return True
    return False
