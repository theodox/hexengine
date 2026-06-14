"""
Hexdemo combat arc graph (authoritative FSM for this title).

Read this module first to understand post-attack flow. Policy (when guards fire and
what effects mutate) lives in ``rules.py``; gate ``ui_mode`` strings in
``transitions.py``; presentation rows in ``ui/segment_registry.py``.

Graph (entry ``classify`` so cleanup-only opens work when bucket state is already set):

```text
attack --Attack--> classify
classify --auto--> retreat_or_disrupt_gate | retreat_gate | advance_gate | done
retreat_gate --MoveUnit (retreat)--> resolve
retreat_or_disrupt_gate --MoveUnit (retreat) / Disrupt--> resolve
resolve --auto--> retreat_gate | advance_gate | done
advance_gate --Advance / advance MoveUnit / Decline--> done
```

Segment → binding (guards/effects wired here; implementations in ``rules.BINDING``):

| Segment | Owner | ui_mode (gates) | Policy |
|---------|-------|-----------------|--------|
| attack | current | combat | ``attack_arc_effect`` on Attack |
| classify | none | — | ``disrupt_offered``, ``has_pending_retreat``, ``advance_available``, ``open_advance`` |
| retreat_gate | retreating | awaiting_retreat | ``is_retreat_fulfillment``, ``apply_retreat_step`` |
| retreat_or_disrupt_gate | retreating | awaiting_retreat_or_disrupt | + ``disrupt_instead`` |
| resolve | none | — | re-classify loop |
| advance_gate | current | awaiting_advance | ``is_combat_advance_move``, ``resolve_advance``, ``clear_advance_gate`` |
"""

from __future__ import annotations

from hexengine.arcs.spec import CURRENT, NO_OWNER, Arc, OwnerRef
from hexengine.authoring.builder import arc, case
from hexengine.authoring.patterns.combat import (
    COMBAT_ARC_ID,
    OWNER_RETREATING,
    SEG_ADVANCE_GATE,
    SEG_ATTACK,
    SEG_CLASSIFY,
    SEG_RESOLVE,
    SEG_RETREAT_GATE,
    SEG_RETREAT_OR_DISRUPT_GATE,
    CombatArcEffectsBinding,
    CombatArcGateUiModes,
    Effect,
)

__all__ = [
    "SEG_ADVANCE_GATE",
    "SEG_ATTACK",
    "SEG_CLASSIFY",
    "SEG_RESOLVE",
    "SEG_RETREAT_GATE",
    "SEG_RETREAT_OR_DISRUPT_GATE",
    "build_hexdemo_combat_arc",
]


def build_hexdemo_combat_arc(
    effects: CombatArcEffectsBinding,
    gates: CombatArcGateUiModes,
    *,
    arc_id: str = COMBAT_ARC_ID,
    attack_effect: Effect | None = None,
    attack_ui_mode: str = "combat",
) -> Arc:
    """Build the hexdemo combat ``Arc`` (optional attack segment + cleanup subgraph)."""

    with arc(arc_id, entry=SEG_CLASSIFY) as a:
        if attack_effect is not None:
            with a.segment(
                SEG_ATTACK,
                owner=CURRENT,
                ui_mode=str(attack_ui_mode),
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
            ui_mode=gates.awaiting_retreat,
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
            ui_mode=gates.awaiting_retreat_or_disrupt,
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
            ui_mode=gates.awaiting_advance,
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
