"""
Hexdemo map overlay specs (engine client renders DOM from ``StateUpdate.map_overlays``).
"""

from __future__ import annotations

from hexengine.hooks import DEFAULT
from hexengine.state import GameState

from ..constants import PACK_STATE_EXTENSION_KEY


def _glyph_row(hex_dict: dict) -> dict[str, object] | None:
    if not isinstance(hex_dict, dict):
        return None
    try:
        hi = int(hex_dict["i"])
        hj = int(hex_dict["j"])
        hk = int(hex_dict["k"])
    except (KeyError, TypeError, ValueError):
        return None
    return {"i": hi, "j": hj, "k": hk}


def map_overlays(
    state: GameState, _viewer_faction: str | None
) -> list[dict[str, object]] | object:
    """
    After combat, show a marker on defender hex(es) (even if defenders were destroyed).
    """
    hx = state.extension.get(PACK_STATE_EXTENSION_KEY)
    if not isinstance(hx, dict):
        return DEFAULT
    atk_n = 0
    prev_attacks = hx.get("attacks_this_phase")
    if isinstance(prev_attacks, list):
        atk_n = len(prev_attacks)
    lc = hx.get("last_combat")
    if not isinstance(lc, dict):
        return DEFAULT

    rows = lc.get("defender_hexes")
    if isinstance(rows, list) and rows:
        overlays: list[dict[str, object]] = []
        for idx, raw in enumerate(rows):
            hxw = _glyph_row(raw) if isinstance(raw, dict) else None
            if hxw is None:
                continue
            overlays.append(
                {
                    "schema": 1,
                    "id": f"hexdemo-last-combat-target-{atk_n}-{idx}",
                    "kind": "glyph",
                    "hex": hxw,
                    "text": "🟎",
                    "css_class": "hexdemo-combat-glyph-overlay",
                }
            )
        if overlays:
            return overlays

    dh = lc.get("defender_hex")
    hxw = _glyph_row(dh) if isinstance(dh, dict) else None
    if hxw is None:
        return DEFAULT
    return [
        {
            "schema": 1,
            "id": f"hexdemo-last-combat-target-{atk_n}",
            "kind": "glyph",
            "hex": hxw,
            "text": "🟎",
            "css_class": "hexdemo-combat-glyph-overlay",
        }
    ]


__all__ = ["map_overlays"]
