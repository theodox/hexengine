"""Tests for HexColRow as odd-q offset coordinates (bijection with Hex)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hexengine.hexes.types import Hex, HexColRow


def test_hex_to_col_row_to_hex() -> None:
    """Hex -> HexColRow (odd-q) -> Hex round trip."""
    test_hexes = [
        Hex(0, 0, 0),
        Hex(5, -3, -2),
        Hex(-4, 7, -3),
        Hex(12, 2, -14),
        Hex(-10, -10, 20),
        Hex(16, 4, -20),
    ]
    for original_hex in test_hexes:
        col_row = HexColRow.from_hex(original_hex)
        recovered_hex = col_row.to_hex()
        assert original_hex == recovered_hex, (
            f"Round trip failed: {original_hex} -> {col_row} -> {recovered_hex}"
        )
        assert Hex.from_hex_col_row(col_row) == recovered_hex == original_hex


def test_col_row_to_hex_to_col_row() -> None:
    """HexColRow -> Hex -> HexColRow round trip (use from_hex to build valid odd-q pairs)."""
    seeds = [
        Hex(0, 0, 0),
        Hex(2, -1, -1),
        Hex(-3, 5, -2),
        Hex(16, 4, -20),
    ]
    for h in seeds:
        original = HexColRow.from_hex(h)
        back = HexColRow.from_hex(original.to_hex())
        assert original == back, f"{original} -> {original.to_hex()} -> {back}"


def test_odd_q_bijection_on_grid() -> None:
    """Odd-q pairs and hexes are in 1:1 correspondence on a bounded grid."""
    hex_set = {Hex(i, j, -i - j) for i in range(-5, 6) for j in range(-5, 6)}
    col_row_set = {HexColRow.from_hex(h) for h in hex_set}
    hex_set_recovered = {cr.to_hex() for cr in col_row_set}
    assert len(hex_set) == len(col_row_set)
    assert hex_set == hex_set_recovered


def test_comparison_with_cartesian() -> None:
    """Cartesian can collide; odd-q HexColRow matches a unique hex like cube coords."""
    from hexengine.hexes.types import Cartesian

    cart1 = Cartesian(18, 13)
    cart2 = Cartesian(18, 14)
    hex1 = Hex.from_cartesian(cart1)
    hex2 = Hex.from_cartesian(cart2)
    col_row1 = HexColRow.from_hex(hex1)
    col_row2 = HexColRow.from_hex(hex2)
    if hex1 == hex2:
        assert col_row1 == col_row2
