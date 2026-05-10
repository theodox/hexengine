"""
Hexdemo UI hooks.

This is title-authored UI policy for small inspection popups (Enter / double-click).
"""

from __future__ import annotations

from hexengine.hexes.types import HexColRow
from hexengine.hooks import DEFAULT
from hexengine.state import GameState


def popup_message(
    state: GameState,
    viewer_faction: str | None,
    target_kind: str,
    target_id: str,
) -> dict[str, object] | object:
    """
    Return a small popup descriptor dict for the given inspect target.

    Keys:
    - text (required): popup label
    - kind (optional): "info" | "error" | ...
    - ttl_ms (optional): client-side lifetime
    - css_class (optional): extra CSS class name
    """
    tk = str(target_kind)
    tid = str(target_id)

    if tk == "unit":
        u = state.board.units.get(tid)
        if u is None:
            return {"text": f"{tid} (missing)", "kind": "error", "ttl_ms": 1200}

        cr = HexColRow.from_hex(u.position)
        pos_s = f"[{cr.col}, {cr.row}]"
        # Keep it compact; this is a tiny hover-ish utility, not a full inspector panel.
        parts: list[str] = [f"{u.unit_id}", f"{u.unit_type}", f"{u.faction}", pos_s]
        own = viewer_faction is not None and viewer_faction == u.faction
        hp_s = f"{int(u.health)}" if own else "?"
        html = (
            "<div class='hexdemo-inspect'>"
            f"<div><b>{u.unit_id}</b> <span class='hexdemo-inspect__type'>{u.unit_type}</span></div>"
            f"<div>Faction: <span class='hexdemo-inspect__faction'>{u.faction}</span></div>"
            f"<div>Hex: <span class='hexdemo-inspect__pos'>{pos_s}</span></div>"
            f"<div>HP: <span class='hexdemo-inspect__hp'>{hp_s}</span></div>"
            "</div>"
        )
        # Provide both; client prefers html when present.
        return {"text": " | ".join(parts), "html": html, "kind": "info", "ttl_ms": 1500}

    if tk == "marker":
        # Markers are not in GameState; server provides anchoring separately.
        return {"text": f"marker {tid}", "kind": "info", "ttl_ms": 1200}

    return DEFAULT


__all__ = ["popup_message"]

