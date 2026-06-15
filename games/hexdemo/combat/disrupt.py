"""
Hexdemo combat disrupt policy (stack-wide disruption from CRT rout/disrupt).

CRT resolution builds abstract disrupt anchor unit ids; expand_disrupt_ids turns them
into generic unit_ops for engine ApplyCombatEffects.
"""

from __future__ import annotations

from typing import Any

from hexengine.state import GameState


def expand_disrupt_ids(
    state: GameState, anchor_unit_ids: list[str]
) -> dict[str, Any]:
    """Expand CRT disrupt anchor ids into ApplyCombatEffects unit_ops."""

    unit_ops: list[dict[str, Any]] = []
    patched: set[str] = set()
    seen_anchors: set[str] = set()
    for item in anchor_unit_ids:
        uid = str(item).strip() if isinstance(item, str) else ""
        if not uid or uid in seen_anchors:
            continue
        seen_anchors.add(uid)
        anchor = state.board.units.get(uid)
        if anchor is None or not anchor.active:
            continue
        for u in state.board.active_units_at_hex(anchor.position):
            if u.faction != anchor.faction:
                continue
            u_id = str(u.unit_id)
            if u_id in patched:
                continue
            patched.add(u_id)
            unit_ops.append(
                {"op": "patch", "unit_id": u_id, "values": {"disrupted": True}}
            )
    if not unit_ops:
        return {}
    return {"unit_ops": unit_ops}


__all__ = [
    "expand_disrupt_ids",
]
