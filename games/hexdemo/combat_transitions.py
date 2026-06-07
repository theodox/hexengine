"""
Hexdemo combat transition effects (title-owned).

Combat flow legality and affordances read ``current_segment`` (declared arcs).
Bucket keys ``retreat_obligations``, ``advance``, ``last_combat``, and
``disrupt_instead_offered`` hold match data; segment ``kind`` strings match
``GATE_AWAITING_*`` constants below.

State table (segment ``kind`` on the combat arc cursor):

| Kind | End phase / auto-advance | Attack planning | Typical entry |
|------|--------------------------|-----------------|---------------|
| (routine) | allowed when no retreat obligations | allowed | turn combat slot |
| ``awaiting_retreat`` | blocked | blocked | ``Attack`` retreat outcome |
| ``awaiting_retreat_or_disrupt`` | blocked | blocked | optional disrupt CRT |
| ``awaiting_advance`` | blocked | blocked | post-retreat advance window |

Transitions:

- retreat outcome → obligations + combat arc ``awaiting_retreat`` (classify)
- optional disrupt CRT → ``disrupt_instead_offered`` flag (classify → disrupt gate)
- obligations cleared + policy → ``advance`` payload (classify → advance gate)
- advance move or skip → arc done
"""

from __future__ import annotations

from hexengine.authoring.patterns.combat import CombatArcGateKinds
from hexengine.state import GameState
from hexengine.state.action_manager import StateAction
from hexengine.state.actions import PatchTitleBucket

from . import title_state

# Segment ``kind`` values on gate-bearing combat arc segments.
GATE_AWAITING_RETREAT = "awaiting_retreat"
GATE_AWAITING_RETREAT_OR_DISRUPT = "awaiting_retreat_or_disrupt"
GATE_AWAITING_ADVANCE = "awaiting_advance"

COMBAT_ARC_GATE_KINDS = CombatArcGateKinds(
    awaiting_retreat=GATE_AWAITING_RETREAT,
    awaiting_retreat_or_disrupt=GATE_AWAITING_RETREAT_OR_DISRUPT,
    awaiting_advance=GATE_AWAITING_ADVANCE,
)

GATES_BLOCKING_ROUTINE: frozenset[str] = frozenset(
    {
        GATE_AWAITING_RETREAT,
        GATE_AWAITING_RETREAT_OR_DISRUPT,
        GATE_AWAITING_ADVANCE,
    }
)

# Title bucket keys cleared on phase advance (`after_phase_transition`).
PHASE_SCOPED_COMBAT_KEYS: tuple[str, ...] = (
    "attacks_this_phase",
    "retreat_obligations",
    "disrupt_instead_offered",
    "last_combat",
    "advance",
)


def clear_combat_state_actions(state: GameState) -> list[StateAction]:
    """Actions to drop phase-scoped combat keys from the hexdemo bucket on phase advance."""

    ek = state.title_bucket_key
    if not ek:
        return []
    if not title_state.bucket(state):
        return []
    return [
        PatchTitleBucket(ek, {}, remove_keys=PHASE_SCOPED_COMBAT_KEYS),
    ]


def attack_planning_blocked_reason(state: GameState, player_faction: str) -> str | None:
    """Human-readable block reason for attack plan preview, or ``None`` if allowed."""

    if str(player_faction).strip() != str(state.turn.current_faction).strip():
        return "Not your turn"
    phase = str(state.turn.current_phase).strip()
    if phase not in ("Combat", "Attack"):
        return "Attack planning is only available during Combat"

    from hexengine.arcs.segment_wire import segment_allows_action

    from . import arc_segment

    seg = arc_segment.project_segment_for_faction(state, player_faction)
    if seg is None:
        return None
    if segment_allows_action(seg, "Attack"):
        return None
    kind = str(seg.get("kind", "")).strip()
    if kind == GATE_AWAITING_ADVANCE:
        return "Resolve combat advance before planning an attack"
    if kind in (GATE_AWAITING_RETREAT, GATE_AWAITING_RETREAT_OR_DISRUPT):
        return "Resolve retreat before planning an attack"
    return "Combat obligations must be resolved before planning an attack"


__all__ = [
    "COMBAT_ARC_GATE_KINDS",
    "GATE_AWAITING_ADVANCE",
    "GATE_AWAITING_RETREAT",
    "GATE_AWAITING_RETREAT_OR_DISRUPT",
    "GATES_BLOCKING_ROUTINE",
    "PHASE_SCOPED_COMBAT_KEYS",
    "attack_planning_blocked_reason",
    "clear_combat_state_actions",
]
