"""Hextml import: odd-q offset → axial (matches flat-top HexLayout / iter_map_grid_hexes)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hexengine.hexes.math import (  # noqa: E402
    hextml_offset_odd_q_to_axial,
    shift_axial_ij_cube_coords_to_origin,
)
from tools.import_hextml_map import parse_hextml_html  # noqa: E402


def test_odd_q_round_trip_forward_row() -> None:
    """Offset row used by Hextml: row = j + (i - (i & 1)) // 2 inverts to axial j."""
    for i in range(6):
        for j in range(4):
            row_off = j + (i - (i & 1)) // 2
            ii, jj = hextml_offset_odd_q_to_axial(i, row_off)
            assert (ii, jj) == (i, j), ((i, j), row_off, (ii, jj))


def test_parse_minimal_map_odd_q() -> None:
    html = """
    <section class="map" data-width="2" data-height="2">
      <article class="hexline" data-y="0">
        <div class="hexblock" data-x="0"><div class="hexagon-in2 plain"></div></div>
        <div class="hexblock" data-x="1"><div class="hexagon-in2 plain"></div></div>
      </article>
      <article class="hexline" data-y="1">
        <div class="hexblock" data-x="0"><div class="hexagon-in2 ocean"></div></div>
        <div class="hexblock" data-x="1"><div class="hexagon-in2 ocean"></div></div>
      </article>
    </section>
    """
    p = parse_hextml_html(html, coord_mode="odd_q")
    cells = p["cells"]
    by_pos = {(c[0], c[1]): c[3] for c in cells}
    assert len(cells) == 4
    assert by_pos[(0, 0)] == "plain"
    assert by_pos[(1, 0)] == "plain"
    assert by_pos[(0, 1)] == "ocean"
    assert by_pos[(1, 1)] == "ocean"


def test_parse_staggered_row_odd_q() -> None:
    """One offset row can hold (0,1), (1,1), and (2,0) — raw i,j would misread (2,0)."""
    html = """
    <section class="map" data-width="3" data-height="2">
      <article class="hexline" data-y="0">
        <div class="hexblock" data-x="0"><div class="hexagon-in2 a"></div></div>
        <div class="hexblock" data-x="1"><div class="hexagon-in2 b"></div></div>
      </article>
      <article class="hexline" data-y="1">
        <div class="hexblock" data-x="0"><div class="hexagon-in2 c"></div></div>
        <div class="hexblock" data-x="1"><div class="hexagon-in2 d"></div></div>
        <div class="hexblock" data-x="2"><div class="hexagon-in2 e"></div></div>
      </article>
    </section>
    """
    p = parse_hextml_html(html, coord_mode="odd_q")
    by_pos = {(c[0], c[1]): c[3] for c in p["cells"]}
    assert by_pos[(0, 0)] == "a"
    assert by_pos[(1, 0)] == "b"
    assert by_pos[(0, 1)] == "c"
    assert by_pos[(1, 1)] == "d"
    assert by_pos[(2, 0)] == "e"


def test_normalize_shifts_origin() -> None:
    core = [(2, 3, -5), (2, 4, -6)]
    out = shift_axial_ij_cube_coords_to_origin(core)
    assert out[0] == (0, 0, 0)
    assert out[1] == (0, 1, -1)
