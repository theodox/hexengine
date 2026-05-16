from __future__ import annotations

import math

import pytest

from hexengine.hexes.constants import HEX_SIDE_COUNT
from hexengine.hexes.edges import (
    EdgeKey,
    direction_toward_neighbor,
    edge_between,
    edge_keys_along_hex_chain,
    edge_keys_for_shape_path,
    exterior_edge_keys_for_hexes,
    hex_chain_from_ordered_edge_keys,
    incident_edge_keys_for_hexes,
    incident_edge_keys_iter,
    internal_edge_keys_for_hexes,
    polyline_vertices_for_vertex_adjacent_edge_keys,
    shared_edge_side_midpoint,
    stitch_vertex_adjacent_edges_along_spine,
)
from hexengine.hexes.math import neighbor_hex
from hexengine.hexes.types import Hex, HexColRow
from hexengine.map.layout import HexLayout


def test_edge_between_none_when_not_adjacent() -> None:
    a = Hex(0, 0, 0)
    b = Hex(2, -1, -1)
    assert edge_between(a, b) is None


def test_edge_between_canonical_order() -> None:
    a = Hex(1, 0, -1)
    b = Hex(0, 0, 0)
    e1 = edge_between(a, b)
    e2 = edge_between(b, a)
    assert e1 is not None and e2 is not None
    assert e1 == e2
    assert e1.hex_low == b and e1.hex_high == a


def test_edge_key_constructor_normalizes_order() -> None:
    a = Hex(1, 0, -1)
    b = Hex(0, 0, 0)
    e = EdgeKey(a, b)
    assert e.hex_low == b and e.hex_high == a


def test_direction_toward_neighbor_round_trip() -> None:
    h = Hex(3, -1, -2)
    for d in range(HEX_SIDE_COUNT):
        n = neighbor_hex(h, d)
        assert direction_toward_neighbor(h, n) == d


def test_direction_toward_neighbor_raises() -> None:
    with pytest.raises(ValueError):
        direction_toward_neighbor(Hex(0, 0, 0), Hex(2, 0, -2))


def test_edge_keys_along_hex_chain_and_shape_path() -> None:
    a = Hex(0, 0, 0)
    b = Hex(1, 0, -1)
    c = Hex(1, -1, 0)
    d0 = direction_toward_neighbor(a, b)
    d1 = direction_toward_neighbor(c, b)
    keys = edge_keys_along_hex_chain((a, b, c), start_side=d0, end_side=d1)
    assert len(keys) == 2
    assert keys[0] == edge_between(a, b)
    assert keys[1] == edge_between(b, c)

    keys2 = edge_keys_for_shape_path(
        (HexColRow(0, 0), HexColRow(1, 0), HexColRow(1, -1)),
        start_side=d0,
        end_side=d1,
        expand=True,
    )
    assert keys2 == keys

    with pytest.raises(ValueError, match="start_side"):
        edge_keys_along_hex_chain((a, b, c), start_side=(d0 + 1) % 6)


def test_polyline_spine_closes_gap_on_wide_hex_turn() -> None:
    """120° at one hex: stitched edge keys + vertex welding yield short steps (no arc)."""
    layout = HexLayout(size=40.0, origin_x=50.0, origin_y=50.0, margin=0.0)
    h910 = Hex.from_hex_col_row(HexColRow(9, 10))
    h99 = Hex.from_hex_col_row(HexColRow(9, 9))
    h109 = Hex.from_hex_col_row(HexColRow(10, 9))
    spine = edge_keys_along_hex_chain((h910, h99, h109))
    cells = hex_chain_from_ordered_edge_keys(spine)
    assert cells == (h910, h99, h109)
    stitched = stitch_vertex_adjacent_edges_along_spine(layout, spine)
    pts = polyline_vertices_for_vertex_adjacent_edge_keys(layout, stitched)
    assert len(pts) >= 4
    for i in range(len(pts) - 1):
        d = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        assert d < 45.0, (i, d)


def test_incident_edge_keys_for_hexes_two_neighbors() -> None:
    """Two adjacent hexes share one border; incident set dedupes that edge (6+6-1 keys)."""
    a = Hex(0, 0, 0)
    b = Hex(1, 0, -1)
    keys = incident_edge_keys_for_hexes((a, b))
    assert len(keys) == 11
    assert frozenset(incident_edge_keys_iter((a, b))) == keys
    shared = edge_between(a, b)
    assert shared is not None
    assert shared in keys


def test_internal_edge_keys_for_hexes() -> None:
    a = Hex(0, 0, 0)
    b = Hex(1, 0, -1)
    c = Hex(2, 0, -2)
    assert internal_edge_keys_for_hexes((a,)) == frozenset()
    ab = edge_between(a, b)
    bc = edge_between(b, c)
    assert ab is not None and bc is not None
    inside = internal_edge_keys_for_hexes((a, b, c))
    assert inside == frozenset({ab, bc})
    assert inside <= incident_edge_keys_for_hexes((a, b, c))


def test_exterior_edge_keys_for_hexes() -> None:
    a = Hex(0, 0, 0)
    b = Hex(1, 0, -1)
    c = Hex(2, 0, -2)
    inc = incident_edge_keys_for_hexes((a, b, c))
    inn = internal_edge_keys_for_hexes((a, b, c))
    ext = exterior_edge_keys_for_hexes((a, b, c))
    assert ext == frozenset(inc - inn)
    assert ext & inn == frozenset()
    assert ext | inn == inc
    assert len(exterior_edge_keys_for_hexes((a,))) == 6
    pair_inc = incident_edge_keys_for_hexes((a, b))
    pair_inn = internal_edge_keys_for_hexes((a, b))
    assert (
        len(exterior_edge_keys_for_hexes((a, b))) == len(pair_inc) - len(pair_inn) == 10
    )


def test_shared_edge_side_midpoint_faces_neighbor_hex() -> None:
    """Segment must lie on the hex pair's common side (not the opposite side of hex_low)."""
    layout = HexLayout(size=24.0, origin_x=11.0, origin_y=-3.0, margin=0.0)
    for h in (Hex(0, 0, 0), Hex(9, 5, -14), Hex(3, -1, -2)):
        for d in range(6):
            n = neighbor_hex(h, d)
            ek = edge_between(h, n)
            assert ek is not None
            (x0, y0), (x1, y1) = shared_edge_side_midpoint(layout, ek)
            mid = ((x0 + x1) / 2, (y0 + y1) / 2)
            hc = layout.hex_to_pixel(ek.hex_low)
            nc = layout.hex_to_pixel(ek.hex_high)
            v = (nc[0] - hc[0], nc[1] - hc[1])
            w = (mid[0] - hc[0], mid[1] - hc[1])
            assert v[0] * w[0] + v[1] * w[1] > 1e-6
