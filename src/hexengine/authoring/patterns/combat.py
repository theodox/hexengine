"""
Post-attack combat cleanup arc pattern (classify → retreat → resolve loop → advance).

Title packs inject guards and effects via ``CombatArcEffectsBinding`` and supply
segment ``kind`` strings for gate-bearing segments (parity with the title FSM table).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ...arcs.spec import CURRENT, NO_OWNER, Arc, ArcContext, OwnerRef
from ...state.action_manager import StateAction
from ..builder import arc, case

COMBAT_ARC_ID = "combat"

SEG_ATTACK = "attack"
SEG_CLASSIFY = "classify"
SEG_RETREAT_GATE = "retreat_gate"
SEG_RETREAT_OR_DISRUPT_GATE = "retreat_or_disrupt_gate"
SEG_RESOLVE = "resolve"
SEG_ADVANCE_GATE = "advance_gate"

OWNER_RETREATING = "retreating"

Guard = Callable[[ArcContext], bool]
Effect = Callable[[ArcContext], list[StateAction]]


@dataclass(frozen=True, slots=True)
class CombatArcGateKinds:
    """Segment ``kind`` strings for gate-bearing combat arc segments."""

    awaiting_retreat: str
    awaiting_retreat_or_disrupt: str
    awaiting_advance: str


class CombatArcEffectsBinding(Protocol):
    """Host-bound guards and effects wired into the combat cleanup arc."""

    def has_pending_retreat(self, ctx: ArcContext) -> bool: ...

    def disrupt_offered(self, ctx: ArcContext) -> bool: ...

    def advance_available(self, ctx: ArcContext) -> bool: ...

    def is_retreat_fulfillment(self, ctx: ArcContext) -> bool: ...

    def is_combat_advance_move(self, ctx: ArcContext) -> bool: ...

    def apply_retreat_step(self, ctx: ArcContext) -> list[StateAction]: ...

    def disrupt_instead(self, ctx: ArcContext) -> list[StateAction]: ...

    def open_advance(self, ctx: ArcContext) -> list[StateAction]: ...

    def resolve_advance(self, ctx: ArcContext) -> list[StateAction]: ...

    def clear_advance_gate(self, ctx: ArcContext) -> list[StateAction]: ...


def build_combat_cleanup_arc(
    effects: CombatArcEffectsBinding,
    gates: CombatArcGateKinds,
    *,
    arc_id: str = COMBAT_ARC_ID,
    attack_effect: Effect | None = None,
    attack_kind: str = "combat",
) -> Arc:
    """
    Build the combat arc (optional ``attack`` segment + cleanup subgraph).

    When ``attack_effect`` is set, segment ``attack`` accepts ``Attack`` and hands off to
    ``classify``. Entry stays ``classify`` so ``begin_combat_arc`` can open cleanup-only
    flows after bucket state is already set.

    ``classify`` picks the gate matching what the attack follow-up set. ``resolve`` auto
    re-classifies after each retreat or disrupt step.
    """

    with arc(arc_id, entry=SEG_CLASSIFY) as a:
        if attack_effect is not None:
            with a.segment(
                SEG_ATTACK,
                owner=CURRENT,
                kind=str(attack_kind),
                allowed_actions=frozenset({"Attack"}),
            ) as s:
                s.on("Attack", effect=attack_effect, goto=SEG_CLASSIFY)

        with a.segment(SEG_CLASSIFY, owner=NO_OWNER) as s:
            s.auto_branch(
                case(guard=effects.disrupt_offered, goto=SEG_RETREAT_OR_DISRUPT_GATE),
                case(guard=effects.has_pending_retreat, goto=SEG_RETREAT_GATE),
                case(
                    guard=effects.advance_available,
                    effect=effects.open_advance,
                    goto=SEG_ADVANCE_GATE,
                ),
                case(done=True),
            )

        with a.segment(
            SEG_RETREAT_GATE,
            owner=OwnerRef(OWNER_RETREATING),
            kind=gates.awaiting_retreat,
        ) as s:
            s.on(
                "MoveUnit",
                guard=effects.is_retreat_fulfillment,
                effect=effects.apply_retreat_step,
                goto=SEG_RESOLVE,
            )

        with a.segment(
            SEG_RETREAT_OR_DISRUPT_GATE,
            owner=OwnerRef(OWNER_RETREATING),
            kind=gates.awaiting_retreat_or_disrupt,
        ) as s:
            s.on(
                "MoveUnit",
                guard=effects.is_retreat_fulfillment,
                effect=effects.apply_retreat_step,
                goto=SEG_RESOLVE,
            )
            s.on(
                "CombatDisruptInsteadOfRetreat",
                effect=effects.disrupt_instead,
                goto=SEG_RESOLVE,
            )

        with a.segment(SEG_RESOLVE, owner=NO_OWNER) as s:
            s.auto_branch(
                case(guard=effects.has_pending_retreat, goto=SEG_RETREAT_GATE),
                case(
                    guard=effects.advance_available,
                    effect=effects.open_advance,
                    goto=SEG_ADVANCE_GATE,
                ),
                case(done=True),
            )

        with a.segment(
            SEG_ADVANCE_GATE,
            owner=CURRENT,
            kind=gates.awaiting_advance,
        ) as s:
            s.on("CombatAdvance", effect=effects.resolve_advance, done=True)
            s.on(
                "MoveUnit",
                guard=effects.is_combat_advance_move,
                effect=effects.resolve_advance,
                done=True,
            )
            s.on("CombatDeclineAdvance", effect=effects.clear_advance_gate, done=True)

    return a.build()


# Plan alias: mandatory retreat obligations then optional advance window.
build_mandatory_retreat_then_optional_advance_arc = build_combat_cleanup_arc

__all__ = [
    "COMBAT_ARC_ID",
    "CombatArcEffectsBinding",
    "CombatArcGateKinds",
    "OWNER_RETREATING",
    "SEG_ADVANCE_GATE",
    "SEG_ATTACK",
    "SEG_CLASSIFY",
    "SEG_RESOLVE",
    "SEG_RETREAT_GATE",
    "SEG_RETREAT_OR_DISRUPT_GATE",
    "build_combat_cleanup_arc",
    "build_mandatory_retreat_then_optional_advance_arc",
]
