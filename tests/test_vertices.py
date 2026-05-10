from __future__ import annotations

from hexengine.hexes.edges import (
    edge_between,
    edge_keys_along_hex_chain,
    hex_chain_from_ordered_edge_keys,
    incident_edge_keys_for_hexes,
    shortest_vertex_adjacent_edge_key_path_within,
    stitch_vertex_adjacent_edges_along_spine,
)
from hexengine.hexes.types import Hex, HexColRow
from hexengine.hexes.vertices import (
    VertexKey,
    shortest_edge_key_path_within_vertex_a_star,
    shortest_edge_key_path_within_vertex_bfs,
    vertex_key_pair_for_edge_key,
    vertex_to_incident_edge_keys,
)
from hexengine.map.layout import HexLayout


def test_vertex_key_pair_round_trip_with_shared_edge_side_midpoint() -> None:
    layout = HexLayout(size=40.0, origin_x=0.0, origin_y=0.0, margin=0.0)
    h0 = Hex(0, 0, 0)
    h1 = Hex(1, 0, -1)
    ek = edge_between(h0, h1)
    assert ek is not None
    a, b = vertex_key_pair_for_edge_key(layout, ek)
    assert a != b
    c0 = VertexKey.from_hex_corner(layout, ek.hex_low, 0)
    assert isinstance(hash(c0), int)


def test_vertex_bfs_matches_edges_shortest_path_api() -> None:
    layout = HexLayout(size=40.0, origin_x=50.0, origin_y=50.0, margin=0.0)
    h910 = Hex.from_hex_col_row(HexColRow(9, 10))
    h99 = Hex.from_hex_col_row(HexColRow(9, 9))
    h109 = Hex.from_hex_col_row(HexColRow(10, 9))
    spine = edge_keys_along_hex_chain((h910, h99, h109))
    turn = hex_chain_from_ordered_edge_keys(spine)[1]
    local = frozenset(e for e in incident_edge_keys_for_hexes((turn,)))
    a, b = spine[0], spine[1]
    p0 = shortest_vertex_adjacent_edge_key_path_within(local, layout, a, b)
    p1 = shortest_edge_key_path_within_vertex_bfs(local, layout, a, b)
    p2 = shortest_edge_key_path_within_vertex_a_star(local, layout, a, b)
    assert p0 == p1 == p2
    assert p0 is not None


def test_stitched_spine_bfs_and_a_star_same_length() -> None:
    layout = HexLayout(size=40.0, origin_x=50.0, origin_y=50.0, margin=0.0)
    h910 = Hex.from_hex_col_row(HexColRow(9, 10))
    h99 = Hex.from_hex_col_row(HexColRow(9, 9))
    h109 = Hex.from_hex_col_row(HexColRow(10, 9))
    spine = edge_keys_along_hex_chain((h910, h99, h109))
    stitched = stitch_vertex_adjacent_edges_along_spine(layout, spine)
    assert len(stitched) >= len(spine)
    bfs = shortest_edge_key_path_within_vertex_bfs(
        frozenset(stitched), layout, stitched[0], stitched[-1]
    )
    ast = shortest_edge_key_path_within_vertex_a_star(
        frozenset(stitched), layout, stitched[0], stitched[-1]
    )
    assert bfs == ast


def test_vertex_to_incident_edge_keys_sorted() -> None:
    layout = HexLayout(24.0, 0.0, 0.0, 0.0)
    a = Hex(0, 0, 0)
    b = Hex(1, 0, -1)
    ek = edge_between(a, b)
    assert ek is not None
    inc = vertex_to_incident_edge_keys(layout, frozenset({ek}))
    assert len(inc) == 2
    for _v, edges in inc.items():
        assert edges == [ek]
