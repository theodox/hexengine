"""
Undirected canonical identity for a shared border between two cube-adjacent hexes.

Direction indices follow neighbor_hex(hex, d) (cube topology).

HexLayout.hex_corners numbers vertices CCW from the +x vertex; that index is not
the same as neighbor direction d. shared_edge_side_midpoint maps d to the
corner-edge index that actually borders the neighbor hex.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

from .constants import HEX_SIDE_COUNT
from .math import distance, neighbor_hex
from .shapes import HexLike, _as_hex
from .shapes import path as shape_path
from .types import Hex

# Flat-top: segment from corners[e] to corners[(e+1) % 6] on hex_low is the shared border
# with neighbor_hex(hex_low, d) when e == _NEIGHBOR_DIR_TO_EDGE[d].
_NEIGHBOR_DIR_TO_EDGE: tuple[int, ...] = (3, 2, 4, 1, 5, 0)


def _hex_sort_tuple(h: Hex) -> tuple[int, int, int]:
    return (h.i, h.j, h.k)


@dataclass(frozen=True)
class EdgeKey:
    """Two cube-adjacent hexes in deterministic (hex_low, hex_high) order."""

    hex_low: Hex
    hex_high: Hex

    def __post_init__(self) -> None:
        lo, hi = self.hex_low, self.hex_high
        if _hex_sort_tuple(lo) > _hex_sort_tuple(hi):
            lo, hi = hi, lo
            object.__setattr__(self, "hex_low", lo)
            object.__setattr__(self, "hex_high", hi)

    @classmethod
    def from_adjacent_hexes(cls, a: Hex, b: Hex) -> EdgeKey:
        """Build canonical key; a and b must differ (not necessarily neighbors)."""
        if _hex_sort_tuple(a) <= _hex_sort_tuple(b):
            return cls(a, b)
        return cls(b, a)


def edge_between(a: Hex, b: Hex) -> EdgeKey | None:
    """Canonical undirected edge for a neighbor step, or None if a and b are not adjacent."""
    if distance(a, b) != 1:
        return None
    return EdgeKey.from_adjacent_hexes(a, b)


def direction_toward_neighbor(from_hex: Hex, neighbor: Hex) -> int:
    """
    Side index d in 0..HEX_SIDE_COUNT-1 with neighbor_hex(from_hex, d) == neighbor.

    Raises ValueError if neighbor is not a cube neighbor of from_hex.
    """
    for d in range(HEX_SIDE_COUNT):
        if neighbor_hex(from_hex, d) == neighbor:
            return d
    raise ValueError(f"{neighbor!r} is not a cube neighbor of {from_hex!r}")


def _dedupe_consecutive(cells: Iterable[Hex]) -> list[Hex]:
    out: list[Hex] = []
    for h in cells:
        if not out or h != out[-1]:
            out.append(h)
    return out


def edge_keys_along_hex_chain(
    cells: Sequence[Hex],
    *,
    start_side: int | None = None,
    end_side: int | None = None,
) -> tuple[EdgeKey, ...]:
    """
    One EdgeKey per consecutive pair in cells (each pair must be neighbors).

    start_side and end_side are optional neighbor_hex direction indices (0..5) on the
    first and last cell:

    - start_side must equal direction_toward_neighbor(cells[0], cells[1]).
    - end_side must equal direction_toward_neighbor(cells[-1], cells[-2]) (the side of
      the terminus that faces the previous cell).
    """
    if len(cells) < 2:
        raise ValueError("cells must contain at least two hexes")
    out: list[EdgeKey] = []
    for i in range(len(cells) - 1):
        a, b = cells[i], cells[i + 1]
        ek = edge_between(a, b)
        if ek is None:
            raise ValueError(f"hexes are not adjacent at index {i}: {a!r}, {b!r}")
        out.append(ek)
    if start_side is not None:
        d0 = direction_toward_neighbor(cells[0], cells[1])
        ss = int(start_side) % HEX_SIDE_COUNT
        if d0 != ss:
            raise ValueError(
                f"start_side {start_side} does not match first step "
                f"(expected neighbor direction {d0} from {cells[0]!r} toward {cells[1]!r})"
            )
    if end_side is not None:
        d1 = direction_toward_neighbor(cells[-1], cells[-2])
        es = int(end_side) % HEX_SIDE_COUNT
        if d1 != es:
            raise ValueError(
                f"end_side {end_side} does not match approach to last hex "
                f"(expected neighbor direction {d1} from {cells[-1]!r} toward {cells[-2]!r})"
            )
    return tuple(out)


def edge_keys_for_shape_path(
    steps: Sequence[HexLike],
    *,
    start_side: int | None = None,
    end_side: int | None = None,
    expand: bool = True,
) -> tuple[EdgeKey, ...]:
    """
    Build edge keys along a path in the same sense as hexes.shapes.path.

    steps lists waypoint cells (Hex, HexColRow, or Cartesian); types may be mixed.

    - With expand=True (default), consecutive waypoints are connected with hexes.math.line
      (same as shapes.path), then consecutive duplicates are removed.
    - With expand=False, steps must already be a chain of cube-adjacent cells (after
      coercing via hexes.shapes._as_hex).

    start_side and end_side are validated like edge_keys_along_hex_chain.
    """
    if len(steps) < 2:
        raise ValueError("steps must contain at least two cells")
    if expand:
        cells = _dedupe_consecutive(shape_path(steps))
    else:
        cells = _dedupe_consecutive(_as_hex(s) for s in steps)
    if len(cells) < 2:
        raise ValueError("path must contain at least two hexes after expansion")
    return edge_keys_along_hex_chain(cells, start_side=start_side, end_side=end_side)


_topology_layout_singleton: object | None = None


def _topology_layout_for_incident_edge_graph() -> object:
    """Fixed HexLayout for quantizing edge segments in the incident-edge graph."""
    global _topology_layout_singleton
    if _topology_layout_singleton is None:
        from ..map.layout import HexLayout

        _topology_layout_singleton = HexLayout(1.0, 0.0, 0.0)
    return _topology_layout_singleton


def _segment_endpoints_quantized(
    layout: object, ek: EdgeKey, *, scale: int = 1_000_000
) -> tuple[tuple[int, int], tuple[int, int]]:
    (x0, y0), (x1, y1) = shared_edge_side_midpoint(layout, ek)
    return (round(x0 * scale), round(y0 * scale)), (
        round(x1 * scale),
        round(y1 * scale),
    )


def edges_share_tiling_vertex(layout: object, a: EdgeKey, b: EdgeKey) -> bool:
    """True if the two map edges share an endpoint in the tiling (same pixel corner)."""
    if a == b:
        return True
    (a0, a1) = _segment_endpoints_quantized(layout, a)
    (b0, b1) = _segment_endpoints_quantized(layout, b)
    return a0 in (b0, b1) or a1 in (b0, b1)


def common_hex_of_adjacent_spine_edges(prev_e: EdgeKey, nxt_e: EdgeKey) -> Hex:
    """The shared hex between consecutive spine edges (center path)."""
    s = {prev_e.hex_low, prev_e.hex_high} & {nxt_e.hex_low, nxt_e.hex_high}
    if len(s) != 1:
        raise ValueError(f"spine edges do not share one hex: {prev_e!r} then {nxt_e!r}")
    return next(iter(s))


def incident_edge_keys_iter(hexes: Iterable[Hex]) -> Iterator[EdgeKey]:
    """Yield each map edge bordering the hex set once (deduped); one O(6|H|) pass."""
    region = frozenset(hexes)
    seen: set[EdgeKey] = set()
    for h in region:
        for d in range(HEX_SIDE_COUNT):
            n = neighbor_hex(h, d)
            ek = edge_between(h, n)
            if ek is None or ek in seen:
                continue
            seen.add(ek)
            yield ek


def incident_edge_keys_for_hexes(hexes: Iterable[Hex]) -> frozenset[EdgeKey]:
    """All map edges incident to any hex in the set; internal borders appear once."""
    return frozenset(incident_edge_keys_iter(hexes))


def internal_edge_keys_for_hexes(hexes: Iterable[Hex]) -> frozenset[EdgeKey]:
    """Edges with both adjacent hexes in the set (filter over incident_edge_keys_iter)."""
    region = frozenset(hexes)
    return frozenset(
        ek
        for ek in incident_edge_keys_iter(region)
        if ek.hex_low in region and ek.hex_high in region
    )


def exterior_edge_keys_for_hexes(hexes: Iterable[Hex]) -> frozenset[EdgeKey]:
    """Boundary edges: one endpoint in the set, one outside (incident minus internal)."""
    region = frozenset(hexes)
    all_touching = frozenset(incident_edge_keys_iter(region))
    inside = frozenset(
        ek for ek in all_touching if ek.hex_low in region and ek.hex_high in region
    )
    return frozenset(all_touching - inside)


def edge_key_sort_tuple(
    ek: EdgeKey,
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Stable sort key for EdgeKey lists."""
    return (_hex_sort_tuple(ek.hex_low), _hex_sort_tuple(ek.hex_high))


def shortest_vertex_adjacent_edge_key_path_within(
    allowed: frozenset[EdgeKey] | set[EdgeKey],
    layout: object | None,
    start: EdgeKey,
    goal: EdgeKey,
) -> tuple[EdgeKey, ...] | None:
    """Shortest walk from start to goal through allowed edges (vertex adjacency)."""
    from . import vertices as _vx

    lay = layout if layout is not None else _topology_layout_for_incident_edge_graph()
    return _vx.shortest_edge_key_path_within_vertex_bfs(allowed, lay, start, goal)


def stitch_vertex_adjacent_edges_along_spine(
    layout: object | None, spine: tuple[EdgeKey, ...]
) -> tuple[EdgeKey, ...]:
    """Walk spine; insert shortest detours on the turn hex where corners do not meet."""
    lay = layout if layout is not None else _topology_layout_for_incident_edge_graph()
    if not spine:
        return ()
    out: list[EdgeKey] = [spine[0]]
    for i in range(len(spine) - 1):
        a, b = spine[i], spine[i + 1]
        if edges_share_tiling_vertex(lay, a, b):
            if out[-1] != b:
                out.append(b)
            continue
        turn = common_hex_of_adjacent_spine_edges(a, b)
        local = incident_edge_keys_for_hexes((turn,))
        blocked = set(spine) - {a, b}
        cand_local = frozenset(e for e in local if e not in blocked)
        patch = shortest_vertex_adjacent_edge_key_path_within(cand_local, lay, a, b)
        if patch is None:
            patch = shortest_vertex_adjacent_edge_key_path_within(local, lay, a, b)
        if patch is None:
            raise ValueError(
                f"cannot vertex-connect spine edges {a!r} and {b!r} along hex {turn!r}"
            )
        if patch[0] != a:
            raise ValueError("internal error: patch must start at first spine edge")
        out.extend(patch[1:])
    deduped: list[EdgeKey] = []
    for ek in out:
        if not deduped or deduped[-1] != ek:
            deduped.append(ek)
    return tuple(deduped)


def shortest_edge_key_path_for_hex_spine(
    cells: Sequence[Hex],
    layout: object | None,
    start: EdgeKey,
    goal: EdgeKey,
    *,
    spine: tuple[EdgeKey, ...] | None = None,
) -> tuple[EdgeKey, ...] | None:
    """Stitched spine; None if start/goal do not match stitched endpoints."""
    lay = layout if layout is not None else _topology_layout_for_incident_edge_graph()
    spine_keys = spine if spine is not None else edge_keys_along_hex_chain(tuple(cells))
    keys = stitch_vertex_adjacent_edges_along_spine(lay, spine_keys)
    if keys[0] != start or keys[-1] != goal:
        return None
    return keys


def _d2_point_to_segment_sq(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    ax, ay, bx, by, px, py = a[0], a[1], b[0], b[1], p[0], p[1]
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    den = vx * vx + vy * vy
    if den <= 1e-30:
        return _dist2_pix(p, a)
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / den))
    qx, qy = ax + t * vx, ay + t * vy
    return (px - qx) * (px - qx) + (py - qy) * (py - qy)


def _tiling_junction_between_edge_segments(
    layout: object,
    prev_e: EdgeKey,
    cur_e: EdgeKey,
    prev_p0: tuple[float, float],
    prev_p1: tuple[float, float],
    cur_p0: tuple[float, float],
    cur_p1: tuple[float, float],
    tol_sq: float,
) -> tuple[float, float] | None:
    """A hex corner lying (within tol) on both segment lines, if any."""
    for h in (prev_e.hex_low, prev_e.hex_high, cur_e.hex_low, cur_e.hex_high):
        for c in layout.hex_corners(h):
            if _d2_point_to_segment_sq(c, prev_p0, prev_p1) <= tol_sq:
                if _d2_point_to_segment_sq(c, cur_p0, cur_p1) <= tol_sq:
                    return c
    return None


def polyline_vertices_for_vertex_adjacent_edge_keys(
    layout: object, keys: Sequence[EdgeKey]
) -> tuple[tuple[float, float], ...]:
    """Pixel polyline through keys; corners from shared_edge_side_midpoint, oriented along path."""
    if not keys:
        return ()
    size = float(getattr(layout, "size", 1.0))
    eps2 = max(1e-8, (max(1.0, size) * 1e-5) ** 2)
    tol_line_sq = max(1e-6, (max(1.0, size) * 1e-4) ** 2)
    out: list[tuple[float, float]] = []
    prev_seg: tuple[tuple[float, float], tuple[float, float], EdgeKey] | None = None

    def append_pt(p: tuple[float, float]) -> None:
        if not out or _dist2_pix(out[-1], p) > eps2:
            out.append(p)

    for idx, ek in enumerate(keys):
        p0, p1 = shared_edge_side_midpoint(layout, ek)
        if not out:
            if idx == len(keys) - 1:
                append_pt(p0)
                append_pt(p1)
                prev_seg = (p0, p1, ek)
                continue
            n0, n1 = shared_edge_side_midpoint(layout, keys[idx + 1])
            cand_a = (p0, p1)
            cand_b = (p1, p0)
            da = min(_dist2_pix(cand_a[1], n0), _dist2_pix(cand_a[1], n1))
            db = min(_dist2_pix(cand_b[1], n0), _dist2_pix(cand_b[1], n1))
            start, end = cand_a if da <= db else cand_b
            append_pt(start)
            append_pt(end)
            prev_seg = (p0, p1, ek)
            continue

        last = out[-1]
        if prev_seg is not None:
            pp0, pp1, pe = prev_seg
            j = _tiling_junction_between_edge_segments(
                layout, pe, ek, pp0, pp1, p0, p1, tol_line_sq
            )
            if j is not None and _dist2_pix(last, j) > eps2:
                append_pt(j)
                last = out[-1]
        if _dist2_pix(last, p0) <= eps2:
            append_pt(p1)
        elif _dist2_pix(last, p1) <= eps2:
            append_pt(p0)
        else:
            closer, farther = (
                (p0, p1) if _dist2_pix(last, p0) <= _dist2_pix(last, p1) else (p1, p0)
            )
            append_pt(closer)
            append_pt(farther)
        prev_seg = (p0, p1, ek)
    return tuple(out)


def hex_chain_from_ordered_edge_keys(keys: Sequence[EdgeKey]) -> tuple[Hex, ...]:
    """
    Recover ordered hex centers for a path produced by edge_keys_along_hex_chain.

    Consecutive keys must share exactly one hex.
    """
    if not keys:
        return ()
    if len(keys) == 1:
        k0 = keys[0]
        return (k0.hex_low, k0.hex_high)
    s0 = {keys[0].hex_low, keys[0].hex_high}
    s1 = {keys[1].hex_low, keys[1].hex_high}
    common = s0 & s1
    if len(common) != 1:
        raise ValueError("edge keys are not a consecutive chain (first pair)")
    h1 = next(iter(common))
    h0 = keys[0].hex_high if keys[0].hex_low == h1 else keys[0].hex_low
    out: list[Hex] = [h0, h1]
    for idx in range(1, len(keys)):
        cur = keys[idx]
        hi = out[-1]
        nxt = cur.hex_high if cur.hex_low == hi else cur.hex_low
        out.append(nxt)
    return tuple(out)


def _dist2_pix(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def shared_edge_side_midpoint(
    layout: object, edge: EdgeKey
) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    Endpoints of the shared border segment in map/pixel space (HexLayout).

    Uses the side of hex_low that faces hex_high so the segment matches grid geometry.
    """
    d = direction_toward_neighbor(edge.hex_low, edge.hex_high)
    e = _NEIGHBOR_DIR_TO_EDGE[d % HEX_SIDE_COUNT]
    corners = layout.hex_corners(edge.hex_low)
    p0 = corners[e]
    p1 = corners[(e + 1) % HEX_SIDE_COUNT]
    return (p0, p1)
