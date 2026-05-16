"""Hex corner keys and edge-path search; board identity stays EdgeKey in edges."""

from __future__ import annotations

import heapq
from collections import defaultdict, deque
from dataclasses import dataclass

from .constants import HEX_SIDE_COUNT
from .edges import EdgeKey
from .types import Hex

_DEFAULT_QUANT_SCALE = 1_000_000


@dataclass(frozen=True)
class VertexKey:
    """Quantized layout pixel (qx, qy); build via from_pixel / from_hex_corner."""

    qx: int
    qy: int

    @classmethod
    def from_pixel(
        cls, x: float, y: float, *, scale: int = _DEFAULT_QUANT_SCALE
    ) -> VertexKey:
        return cls(round(float(x) * scale), round(float(y) * scale))

    @classmethod
    def from_hex_corner(
        cls,
        layout: object,
        h: Hex,
        corner_index: int,
        *,
        scale: int = _DEFAULT_QUANT_SCALE,
    ) -> VertexKey:
        """Corner index mod 6 on h in layout pixel space."""
        corners = layout.hex_corners(h)
        x, y = corners[int(corner_index) % HEX_SIDE_COUNT]
        return cls.from_pixel(x, y, scale=scale)


def vertex_key_pair_for_edge_key(
    layout: object, ek: EdgeKey, *, scale: int = _DEFAULT_QUANT_SCALE
) -> tuple[VertexKey, VertexKey]:
    """Endpoints of ek's shared side as VertexKeys (unordered)."""
    from .edges import shared_edge_side_midpoint

    (x0, y0), (x1, y1) = shared_edge_side_midpoint(layout, ek)
    return (
        VertexKey.from_pixel(x0, y0, scale=scale),
        VertexKey.from_pixel(x1, y1, scale=scale),
    )


def _canonical_vertex_pair(a: VertexKey, b: VertexKey) -> tuple[VertexKey, VertexKey]:
    if (a.qx, a.qy) <= (b.qx, b.qy):
        return (a, b)
    return (b, a)


def _vertex_graph_from_allowed(
    layout: object, cand: frozenset[EdgeKey], *, scale: int = _DEFAULT_QUANT_SCALE
) -> tuple[
    dict[tuple[VertexKey, VertexKey], EdgeKey], dict[VertexKey, list[VertexKey]]
]:
    pair_to_ek: dict[tuple[VertexKey, VertexKey], EdgeKey] = {}
    adj: dict[VertexKey, list[VertexKey]] = defaultdict(list)
    for ek in cand:
        a, b = vertex_key_pair_for_edge_key(layout, ek, scale=scale)
        pk = _canonical_vertex_pair(a, b)
        pair_to_ek[pk] = ek
        adj[a].append(b)
        adj[b].append(a)
    for v in adj:
        adj[v].sort(key=lambda u: (u.qx, u.qy))
    return pair_to_ek, dict(adj)


def _vertex_bfs_directed_start(
    pair_to_ek: dict[tuple[VertexKey, VertexKey], EdgeKey],
    adj: dict[VertexKey, list[VertexKey]],
    seed: VertexKey,
    from_v: VertexKey,
    start_ek: EdgeKey,
    goal_ek: EdgeKey,
    goal_a: VertexKey,
    goal_b: VertexKey,
) -> tuple[EdgeKey, ...] | None:
    """BFS from seed (dist 1) having crossed start_ek from from_v -> seed."""
    if pair_to_ek.get(_canonical_vertex_pair(from_v, seed)) != start_ek:
        return None
    dist: dict[VertexKey, int] = {seed: 1}
    parent: dict[VertexKey, VertexKey] = {seed: from_v}
    dq: deque[VertexKey] = deque([seed])
    relax_cap = max(5000, len(adj) * 40, len(pair_to_ek) * 24)
    relax_count = 0
    while dq:
        v = dq.popleft()
        nbrs = adj.get(v)
        if nbrs is None:
            return None
        pv = parent.get(v)
        if pv is None:
            return None
        for u in nbrs:
            relax_count += 1
            if relax_count > relax_cap:
                return None
            if u == pv:
                continue
            # from_v is only the predecessor of seed (crossed start_ek); do not re-discover
            # it from elsewhere or parent pointers form a cycle and vertex-chain rebuild loops.
            if u == from_v and v != seed:
                continue
            if u not in dist:
                dist[u] = dist[v] + 1
                parent[u] = v
                dq.append(u)

    best: tuple[int, tuple[int, int], tuple[EdgeKey, ...]] | None = None
    for g in (goal_a, goal_b):
        if g not in dist:
            continue
        verts: list[VertexKey] = []
        cur: VertexKey | None = g
        seen_up: set[VertexKey] = set()
        walk_ok = True
        while cur is not None:
            if cur in seen_up:
                walk_ok = False
                break
            seen_up.add(cur)
            verts.append(cur)
            cur = parent.get(cur)
        if not walk_ok:
            continue
        verts.reverse()
        edges: list[EdgeKey] = []
        ok = True
        for i in range(len(verts) - 1):
            pk = _canonical_vertex_pair(verts[i], verts[i + 1])
            ek = pair_to_ek.get(pk)
            if ek is None:
                ok = False
                break
            edges.append(ek)
        if not ok or not edges:
            continue
        if edges[0] != start_ek or edges[-1] != goal_ek:
            continue
        n = len(edges)
        tie = (g.qx, g.qy)
        if best is None or n < best[0] or (n == best[0] and tie < best[1]):
            best = (n, tie, tuple(edges))
    return None if best is None else best[2]


def shortest_edge_key_path_hex_corridor_vertex_space(
    cells: tuple[Hex, ...],
    layout: object | None,
    start_ek: EdgeKey,
    goal_ek: EdgeKey,
    *,
    scale: int = _DEFAULT_QUANT_SCALE,
) -> tuple[EdgeKey, ...] | None:
    """
    Shortest edge walk along borders of path hexes: vertex BFS on
    incident_edge_keys_for_hexes(cells), first edge start_ek, last edge goal_ek.
    """
    from .edges import (
        _topology_layout_for_incident_edge_graph,
        edge_key_sort_tuple,
        incident_edge_keys_for_hexes,
    )

    lay = layout if layout is not None else _topology_layout_for_incident_edge_graph()
    cand = frozenset(incident_edge_keys_for_hexes(frozenset(cells)))
    if start_ek not in cand or goal_ek not in cand:
        return None
    if start_ek == goal_ek:
        return (start_ek,)
    pair_to_ek, adj = _vertex_graph_from_allowed(lay, cand, scale=scale)
    sa, sb = vertex_key_pair_for_edge_key(lay, start_ek, scale=scale)
    ga, gb = vertex_key_pair_for_edge_key(lay, goal_ek, scale=scale)
    out: list[tuple[EdgeKey, ...] | None] = []
    for seed, frm in ((sa, sb), (sb, sa)):
        p = _vertex_bfs_directed_start(
            pair_to_ek,
            adj,
            seed,
            frm,
            start_ek,
            goal_ek,
            ga,
            gb,
        )
        out.append(p)
    candidates = [x for x in out if x is not None]
    if not candidates:
        return None
    return min(
        candidates, key=lambda t: (len(t), tuple(edge_key_sort_tuple(e) for e in t))
    )


def vertex_to_incident_edge_keys(
    layout: object, allowed: frozenset[EdgeKey] | set[EdgeKey]
) -> dict[VertexKey, list[EdgeKey]]:
    """Vertex -> incident edges from allowed; each list sorted for stable BFS."""
    from .edges import edge_key_sort_tuple

    cand = frozenset(allowed)
    vm: dict[VertexKey, list[EdgeKey]] = defaultdict(list)
    for ek in cand:
        a, b = vertex_key_pair_for_edge_key(layout, ek)
        vm[a].append(ek)
        vm[b].append(ek)
    for v in vm:
        vm[v].sort(key=edge_key_sort_tuple)
    return dict(vm)


def _neighbors_edge(
    layout: object,
    ek: EdgeKey,
    vm: dict[VertexKey, list[EdgeKey]],
    *,
    scale: int = _DEFAULT_QUANT_SCALE,
) -> list[EdgeKey]:
    a, b = vertex_key_pair_for_edge_key(layout, ek, scale=scale)
    seen: set[EdgeKey] = set()
    out_n: list[EdgeKey] = []
    for v in (a, b):
        for o in vm[v]:
            if o is ek or o in seen:
                continue
            seen.add(o)
            out_n.append(o)
    return out_n


def shortest_edge_key_path_within_vertex_bfs(
    allowed: frozenset[EdgeKey] | set[EdgeKey],
    layout: object,
    start: EdgeKey,
    goal: EdgeKey,
    *,
    scale: int = _DEFAULT_QUANT_SCALE,
) -> tuple[EdgeKey, ...] | None:
    """Fewest EdgeKey steps between start and goal in the allowed line graph (BFS)."""
    cand = frozenset(allowed)
    if start not in cand or goal not in cand:
        return None
    vm = vertex_to_incident_edge_keys(layout, cand)

    if start == goal:
        return (start,)

    parent: dict[EdgeKey, EdgeKey | None] = {start: None}
    dq: deque[EdgeKey] = deque([start])
    while dq:
        cur = dq.popleft()
        if cur == goal:
            break
        for nb in _neighbors_edge(layout, cur, vm, scale=scale):
            if nb not in parent:
                parent[nb] = cur
                dq.append(nb)
    if goal not in parent:
        return None

    rev: list[EdgeKey] = [goal]
    while rev[-1] != start:
        p = parent.get(rev[-1])
        if p is None:
            return None
        rev.append(p)
    rev.reverse()
    return tuple(rev)


def shortest_edge_key_path_within_vertex_a_star(
    allowed: frozenset[EdgeKey] | set[EdgeKey],
    layout: object,
    start: EdgeKey,
    goal: EdgeKey,
    *,
    scale: int = _DEFAULT_QUANT_SCALE,
) -> tuple[EdgeKey, ...] | None:
    """Same path as BFS; A* uses exact hop distance to goal from a backward BFS."""
    cand = frozenset(allowed)
    if start not in cand or goal not in cand:
        return None
    vm = vertex_to_incident_edge_keys(layout, cand)

    if start == goal:
        return (start,)

    h_score: dict[EdgeKey, int] = {goal: 0}
    dq: deque[EdgeKey] = deque([goal])
    while dq:
        cur = dq.popleft()
        for nb in _neighbors_edge(layout, cur, vm, scale=scale):
            if nb not in h_score:
                h_score[nb] = h_score[cur] + 1
                dq.append(nb)

    if start not in h_score:
        return None

    tie = 0
    heap: list[tuple[int, int, int, EdgeKey]] = []
    g_score: dict[EdgeKey, int] = {start: 0}
    came: dict[EdgeKey, EdgeKey | None] = {start: None}

    def push(g: int, ek: EdgeKey) -> None:
        nonlocal tie
        f = g + h_score[ek]
        tie += 1
        heapq.heappush(heap, (f, tie, g, ek))

    push(0, start)

    while heap:
        _f, _t, g, cur = heapq.heappop(heap)
        if g != g_score.get(cur, -1):
            continue
        if cur == goal:
            rev: list[EdgeKey] = [goal]
            while rev[-1] != start:
                p = came.get(rev[-1])
                if p is None:
                    return None
                rev.append(p)
            rev.reverse()
            return tuple(rev)
        for nb in _neighbors_edge(layout, cur, vm, scale=scale):
            ng = g + 1
            if ng < g_score.get(nb, 1 << 62):
                g_score[nb] = ng
                came[nb] = cur
                push(ng, nb)
    return None
