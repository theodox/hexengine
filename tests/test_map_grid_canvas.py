"""Canvas sizing: tight bbox over explicit hexes vs full axis-aligned rectangle."""

from __future__ import annotations

from hexengine.hexes.types import Hex, HexColRow
from hexengine.map.layout import (
    fit_hex_grid_canvas,
    fit_hex_grid_canvas_for_hexes,
    iter_map_grid_hex_col_rows,
)
from hexengine.scenarios.schema import MapDisplayConfig


def test_explicit_hex_set_canvas_shorter_than_full_rectangle() -> None:
    cols, rows, oi, oj = 5, 9, 0, 0
    hs = 24.0
    subset = list(iter_map_grid_hex_col_rows(cols, 3, origin_col=oi, origin_row=oj))
    _, _cw_r, ch_r = fit_hex_grid_canvas(
        hs,
        cols,
        rows,
        origin_col=oi,
        origin_row=oj,
        margin_pad=0.0,
        stroke_pad=2.0,
    )
    _, _cw_t, ch_t = fit_hex_grid_canvas_for_hexes(
        hs, subset, margin_pad=0.0, stroke_pad=2.0
    )
    assert ch_t < ch_r


def test_map_grid_hex_col_rows_matches_toml_positions() -> None:
    """Board cells are odd-q (col, row), not an axial (i, j) stepping rectangle."""
    cells = {h for h in iter_map_grid_hex_col_rows(2, 2, origin_col=3, origin_row=2)}
    assert cells == {
        Hex.from_hex_col_row(HexColRow(3, 2)),
        Hex.from_hex_col_row(HexColRow(4, 2)),
        Hex.from_hex_col_row(HexColRow(3, 3)),
        Hex.from_hex_col_row(HexColRow(4, 3)),
    }


def test_map_display_wire_round_trip_grid_hexes() -> None:
    m = MapDisplayConfig(
        hex_columns=3,
        hex_rows=4,
        grid_hexes=((0, 0, 0), (1, 0, -1)),
        background_crop_to_map=False,
    )
    d = m.to_wire_dict()
    m2 = MapDisplayConfig.from_wire_dict(d)
    assert m2.grid_hexes == m.grid_hexes
    assert m2.background_crop_to_map is False


def test_map_display_background_crop_defaults_true() -> None:
    m = MapDisplayConfig.from_wire_dict({"hex_size": 24.0})
    assert m.background_crop_to_map is True


def test_map_display_from_wire_rejects_bad_grid_hexes() -> None:
    try:
        MapDisplayConfig.from_wire_dict(
            {
                "hex_columns": 1,
                "hex_rows": 1,
                "grid_hexes": [[0, 0]],
            }
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for short triple")
