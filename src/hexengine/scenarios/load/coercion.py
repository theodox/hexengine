"""
Pure TOML value coercions for scenario rows (no parse.py imports).
"""

from __future__ import annotations

from ...hexes.types import Hex, HexColRow


def parse_position(raw: list[int] | tuple[int, ...]) -> tuple[int, int]:
    """
    Parse TOML `position` as odd-q `[col, row]` (`hexengine.hexes.types.HexColRow`).
    """
    if len(raw) != 2:
        raise ValueError(
            f"position must be [col, row] (two integers, odd-q), got {len(raw)} values"
        )
    return (int(raw[0]), int(raw[1]))


def float_or_inf(v: str | float | int) -> float:
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str) and v.strip().lower() in ("inf", "infinity"):
        return float("inf")
    return float(v)


def coerce_movement_cost(raw: str | float | int) -> float:
    """`movement_cost` may be a float or the string `inf`."""
    if isinstance(raw, str):
        return float_or_inf(raw)
    return float(raw)


def position_to_cube_tuple(pos: tuple[int, int]) -> tuple[int, int, int]:
    """Scenario `Position` → cube triple for `MapDisplayConfig.grid_hexes` / clients."""
    h = Hex.from_hex_col_row(HexColRow(col=pos[0], row=pos[1]))
    return (h.i, h.j, h.k)
