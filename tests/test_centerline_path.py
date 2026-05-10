from __future__ import annotations

import pytest

from hexengine.hexes.centerline import (
    consecutive_step_on_path,
    linear_feature_path_around_hexes,
    perimeter_hex_path,
    silhouette_edge,
    validate_linear_hex_path,
)
from hexengine.hexes.types import Hex, HexColRow


def test_valid_path() -> None:
    p = (Hex(0, 0, 0), Hex(1, 0, -1), Hex(1, -1, 0))
    validate_linear_hex_path(p)


def test_invalid_path_gap() -> None:
    with pytest.raises(ValueError, match="not a neighbor"):
        validate_linear_hex_path((Hex(0, 0, 0), Hex(2, 0, -2)))


def test_consecutive_step_on_path_bidirectional() -> None:
    p = (Hex(0, 0, 0), Hex(1, 0, -1), Hex(1, -1, 0))
    assert consecutive_step_on_path(p, Hex(0, 0, 0), Hex(1, 0, -1))
    assert consecutive_step_on_path(p, Hex(1, 0, -1), Hex(0, 0, 0))
    assert not consecutive_step_on_path(p, Hex(0, 0, 0), Hex(1, -1, 0))


def test_silhouette_edge_interior_vs_outline() -> None:
    a, b = Hex(0, 0, 0), Hex(1, 0, -1)
    block = frozenset(
        [
            a,
            b,
            Hex(0, 1, -1),
            Hex(1, 1, -2),
        ]
    )
    assert silhouette_edge(a, b, block) is False
    thin = frozenset([a, b])
    assert silhouette_edge(a, b, thin) is True


def test_perimeter_two_hexes_open_chain() -> None:
    a, b = Hex(0, 0, 0), Hex(1, 0, -1)
    assert perimeter_hex_path(frozenset([a, b])) == (a, b)


def test_perimeter_three_line_open_chain() -> None:
    h0, h1, h2 = Hex(0, 0, 0), Hex(1, 0, -1), Hex(2, 0, -2)
    assert perimeter_hex_path(frozenset([h0, h1, h2])) == (h0, h1, h2)


def test_perimeter_l_shape_closed() -> None:
    h0, h1, h2 = Hex(0, 0, 0), Hex(1, 0, -1), Hex(0, 1, -1)
    path = perimeter_hex_path(frozenset([h0, h1, h2]))
    assert path[0] == path[-1]
    assert len(path) == 4
    validate_linear_hex_path(path)


def test_perimeter_two_by_two_closed() -> None:
    hs = [
        Hex(0, 0, 0),
        Hex(1, 0, -1),
        Hex(0, 1, -1),
        Hex(1, 1, -2),
    ]
    path = perimeter_hex_path(frozenset(hs))
    assert path[0] == path[-1]
    assert len(set(path)) == 4
    validate_linear_hex_path(path)


def test_linear_feature_path_around_hexes_mixed_hex_like() -> None:
    a, b = Hex(0, 0, 0), Hex(1, 0, -1)
    lf = linear_feature_path_around_hexes([a, HexColRow(col=1, row=0)])
    assert lf.hexes == (a, b)


def test_perimeter_too_small_raises() -> None:
    with pytest.raises(ValueError, match="at least two"):
        perimeter_hex_path(frozenset([Hex(0, 0, 0)]))


def test_perimeter_disjoint_raises() -> None:
    d = frozenset(
        [
            Hex(0, 0, 0),
            Hex(1, 0, -1),
            Hex(5, 0, -5),
            Hex(6, 0, -6),
        ]
    )
    with pytest.raises(ValueError, match="single loop"):
        perimeter_hex_path(d)
