"""
Hexdemo map overlay specs (engine client renders DOM from `StateUpdate.map_overlays`).
"""

from __future__ import annotations

from hexengine.authoring.present import map_overlay_glyph
from hexengine.hooks.ui import ENGINE_DEFAULT, UIHook
from hexengine.hooks.wiring import bind_title_hook
from hexengine.state import GameState
from hexengine.ui.display import MapOverlay

from .. import session_state

_COMBAT_GLYPH = "🟎"
_COMBAT_GLYPH_CLASS = "hexdemo-combat-glyph-overlay"


def _hex_coords(raw: dict) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    try:
        return {
            "i": int(raw["i"]),
            "j": int(raw["j"]),
            "k": int(raw["k"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _glyph_overlay(overlay_id: str, hex_dict: dict) -> MapOverlay | None:
    hxw = _hex_coords(hex_dict)
    if hxw is None:
        return None
    return map_overlay_glyph(
        id=overlay_id,
        hex=hxw,
        text=_COMBAT_GLYPH,
        css_class=_COMBAT_GLYPH_CLASS,
    )


@bind_title_hook(UIHook.MAP_OVERLAYS)
def map_overlays(
    state: GameState, _viewer_faction: str | None
) -> list[MapOverlay] | object:
    """
    After combat, show a marker on defender hex(es) (even if defenders were destroyed).
    """
    if not session_state.bucket(state):
        return ENGINE_DEFAULT
    atk_n = len(session_state.attacks_this_phase(state))
    lc = session_state.last_combat(state)
    if lc is None:
        return ENGINE_DEFAULT

    rows = lc.get("defender_hexes")
    if isinstance(rows, list) and rows:
        overlays: list[MapOverlay] = []
        for idx, raw in enumerate(rows):
            if not isinstance(raw, dict):
                continue
            row = _glyph_overlay(f"hexdemo-last-combat-target-{atk_n}-{idx}", raw)
            if row is not None:
                overlays.append(row)
        if overlays:
            return overlays

    dh = lc.get("defender_hex")
    if not isinstance(dh, dict):
        return ENGINE_DEFAULT
    row = _glyph_overlay(f"hexdemo-last-combat-target-{atk_n}", dh)
    if row is None:
        return ENGINE_DEFAULT
    return [row]


__all__ = ["map_overlays"]
