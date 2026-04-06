"""Tests for HexRowCol as odd-q offset coordinates (bijection with Hex)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hexengine.hexes.types import Hex, HexRowCol


def test_hex_to_rowcol_to_hex() -> None:
    """Hex -> HexRowCol (odd-q) -> Hex round trip."""
    test_hexes = [
        Hex(0, 0, 0),
        Hex(5, -3, -2),
        Hex(-4, 7, -3),
        Hex(12, 2, -14),
        Hex(-10, -10, 20),
        Hex(16, 4, -20),
    ]
    for original_hex in test_hexes:
        rowcol = HexRowCol.from_hex(original_hex)
        recovered_hex = rowcol.to_hex()
        assert original_hex == recovered_hex, (
            f"Round trip failed: {original_hex} -> {rowcol} -> {recovered_hex}"
        )
        assert Hex.from_hex_row_col(rowcol) == recovered_hex == original_hex


def test_rowcol_to_hex_to_rowcol() -> None:
    """HexRowCol -> Hex -> HexRowCol round trip (use from_hex to build valid odd-q pairs)."""
    seeds = [
        Hex(0, 0, 0),
        Hex(2, -1, -1),
        Hex(-3, 5, -2),
        Hex(16, 4, -20),
    ]
    for h in seeds:
        original = HexRowCol.from_hex(h)
        back = HexRowCol.from_hex(original.to_hex())
        assert original == back, f"{original} -> {original.to_hex()} -> {back}"


def test_odd_q_bijection_on_grid() -> None:
    """Odd-q pairs and hexes are in 1:1 correspondence on a bounded grid."""
    hex_set = {Hex(i, j, -i - j) for i in range(-5, 6) for j in range(-5, 6)}
    rowcol_set = {HexRowCol.from_hex(h) for h in hex_set}
    hex_set_recovered = {rc.to_hex() for rc in rowcol_set}
    assert len(hex_set) == len(rowcol_set)
    assert hex_set == hex_set_recovered


def test_comparison_with_cartesian() -> None:
    """Cartesian can collide; odd-q HexRowCol matches a unique hex like cube coords."""
    from hexengine.hexes.types import Cartesian

    cart1 = Cartesian(18, 13)
    cart2 = Cartesian(18, 14)
    hex1 = Hex.from_cartesian(cart1)
    hex2 = Hex.from_cartesian(cart2)
    rowcol1 = HexRowCol.from_hex(hex1)
    rowcol2 = HexRowCol.from_hex(hex2)
    if hex1 == hex2:
        assert rowcol1 == rowcol2
