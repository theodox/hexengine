"""Canvas sizing: tight bbox over explicit hexes vs full axis-aligned rectangle."""

from __future__ import annotations

from hexengine.map.layout import (
    fit_hex_grid_canvas,
    fit_hex_grid_canvas_for_hexes,
    iter_map_grid_hexes,
)
from hexengine.scenarios.schema import MapDisplayConfig


def test_explicit_hex_set_canvas_shorter_than_full_rectangle() -> None:
    cols, rows, oi, oj = 5, 9, 0, 0
    hs = 24.0
    subset = list(iter_map_grid_hexes(cols, 3, oi, oj))
    _, _cw_r, ch_r = fit_hex_grid_canvas(
        hs, cols, rows, origin_i=oi, origin_j=oj, margin_pad=0.0, stroke_pad=2.0
    )
    _, _cw_t, ch_t = fit_hex_grid_canvas_for_hexes(
        hs, subset, margin_pad=0.0, stroke_pad=2.0
    )
    assert ch_t < ch_r


def test_map_display_wire_round_trip_grid_hexes() -> None:
    m = MapDisplayConfig(
        hex_columns=3,
        hex_rows=4,
        grid_hexes=((0, 0, 0), (1, 0, -1)),
    )
    d = m.to_wire_dict()
    m2 = MapDisplayConfig.from_wire_dict(d)
    assert m2.grid_hexes == m.grid_hexes


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
