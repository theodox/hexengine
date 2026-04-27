"""
Hexdemo map overlay specs (engine client renders DOM from ``StateUpdate.map_overlays``).
"""

from __future__ import annotations

from hexengine.hooks import DEFAULT
from hexengine.state import GameState

from ..constants import PACK_STATE_EXTENSION_KEY


def map_overlays(state: GameState, _viewer_faction: str | None) -> list[dict[str, object]] | object:
    """
    After combat, show a marker on the defender hex (even if the defender was destroyed).
    """
    hx = state.extension.get(PACK_STATE_EXTENSION_KEY)
    if not isinstance(hx, dict):
        return DEFAULT
    # Use a changing id per combat event so glyph CSS animations can replay.
    # (If we keep a stable id, the client updates the same DOM node and any
    # `visibility: hidden` / finished animation state can persist across attacks.)
    atk_n = 0
    prev_attacks = hx.get("attacks_this_phase")
    if isinstance(prev_attacks, list):
        atk_n = len(prev_attacks)
    lc = hx.get("last_combat")
    if not isinstance(lc, dict):
        return DEFAULT
    dh = lc.get("defender_hex")
    if not isinstance(dh, dict):
        return DEFAULT
    try:
        int(dh["i"])
        int(dh["j"])
        int(dh["k"])
    except (KeyError, TypeError, ValueError):
        return DEFAULT
    return [
        {
            "schema": 1,
            "id": f"hexdemo-last-combat-target-{atk_n}",
            "kind": "glyph",
            "hex": {"i": int(dh["i"]), "j": int(dh["j"]), "k": int(dh["k"])},
            "text": "🟎",
            "css_class": "hexdemo-combat-glyph-overlay",
        }
    ]


__all__ = ["map_overlays"]
