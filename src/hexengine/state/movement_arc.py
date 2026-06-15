"""Engine-reserved `GameState.extension` keys for multi-step movement **arcs**.

Vocabulary (cross-cutting, engine + client):

**Arc**
    A server-orchestrated multi-step **authority** unit that occupies part of a turn
    (and may temporarily hand action to other factions). Combat cleanup
    (attack → mandatory retreat / disrupt → optional advance) and stepwise movement
    (under `HEXENGINE_MOVEMENT_ARC_KEY`) are arcs. Thin clients may mirror the same
    idea as **Arc** without implying local authority.

**Segment**
    One **step** inside an arc—the smallest server-advanced unit along that arc (e.g.
    one hex hop of a stepwise path, one `PassMovementInterrupt`, or one named stage
    of the attack pipeline). The turn arc registry schedules routine segments; overlay
    arcs (combat, movement) suspend that cursor until they finish.

Combat arcs use the title `extension` bucket; movement stepwise state uses this module’s
wire key. Multi-hex retreats open via the movement arc ``retreat_open`` segment after
authority validation; normal stepwise moves may still open inline in
``authority_movement``. ``sync_movement_cursor_from_payload`` aligns the arc cursor with
the payload gate. See ``hexengine.server.arcs.authority_attack`` (attack RPC),
``hexengine.server.arcs.authority_movement`` (stepwise move), and
``hexengine.server.arcs.authority_combat_cleanup`` (disrupt / advance / stacked retreat).
Rationale for retreat reuse is documented on ``movement_arc_decl``.
"""

from __future__ import annotations

from typing import Any

from .game_state import TurnState

HEXENGINE_MOVEMENT_ARC_KEY = "hexengine_movement_arc"

MOVEMENT_ARC_GATE_AWAITING_CONTINUE = "awaiting_continue"
MOVEMENT_ARC_GATE_AWAITING_INTERRUPT = "awaiting_interrupt"

MOVEMENT_INTERRUPT_PHASE = "MovementInterrupt"

MOVEMENT_ARC_SCHEMA = 1


def turn_state_to_movement_arc_snapshot(t: TurnState) -> dict[str, Any]:
    """JSON-safe dict for storing `TurnState` inside a movement **arc** payload."""

    return {
        "current_faction": str(t.current_faction),
        "current_phase": str(t.current_phase),
        "phase_actions_remaining": int(t.phase_actions_remaining),
        "turn_number": int(t.turn_number),
        "schedule_index": int(t.schedule_index),
        "global_tick": int(t.global_tick),
    }


def turn_state_from_movement_arc_snapshot(d: dict[str, Any]) -> TurnState:
    """Inverse of `turn_state_to_movement_arc_snapshot`."""

    return TurnState(
        current_faction=str(d["current_faction"]),
        current_phase=str(d["current_phase"]),
        phase_actions_remaining=int(d["phase_actions_remaining"]),
        turn_number=int(d.get("turn_number", 1)),
        schedule_index=int(d.get("schedule_index", 0)),
        global_tick=int(d.get("global_tick", 0)),
    )


__all__ = [
    "HEXENGINE_MOVEMENT_ARC_KEY",
    "MOVEMENT_ARC_GATE_AWAITING_CONTINUE",
    "MOVEMENT_ARC_GATE_AWAITING_INTERRUPT",
    "MOVEMENT_ARC_SCHEMA",
    "MOVEMENT_INTERRUPT_PHASE",
    "turn_state_from_movement_arc_snapshot",
    "turn_state_to_movement_arc_snapshot",
]
