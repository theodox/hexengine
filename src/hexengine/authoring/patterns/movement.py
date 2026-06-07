"""
Stepwise movement arc pattern (host-bound effects injected at assembly time).
"""

from __future__ import annotations

from ...arcs.movement_arc_decl import (
    MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
    MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
    MOVEMENT_ARC_ID,
    OWNER_MOVING,
    SEG_CONTINUE,
    SEG_INTERRUPT,
    SEG_INTERRUPT_RESOLVE,
    SEG_STEP_RESOLVE,
    MovementArcEffectsBinding,
    interrupt_queue_empty,
    path_complete,
    step_opened_interrupts,
)
from ...arcs.spec import CURRENT, NO_OWNER, Arc, OwnerRef
from ..builder import arc, case


def build_movement_arc(effects: MovementArcEffectsBinding) -> Arc:
    """Build the engine stepwise movement arc (interrupt sub-arc, depth-1 suspend)."""

    with arc(MOVEMENT_ARC_ID, entry=SEG_CONTINUE) as a:
        with a.segment(
            SEG_CONTINUE,
            owner=OwnerRef(OWNER_MOVING),
            kind=MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
        ) as s:
            s.on(
                "MoveUnit",
                guard=effects.matches_stepwise_step,
                effect=effects.apply_step,
                goto=SEG_STEP_RESOLVE,
            )

        with a.segment(SEG_STEP_RESOLVE, owner=NO_OWNER) as s:
            s.auto_branch(
                case(guard=path_complete, effect=effects.finish_path, done=True),
                case(
                    guard=step_opened_interrupts,
                    interrupt=SEG_INTERRUPT,
                    resume_at=SEG_CONTINUE,
                ),
                case(goto=SEG_CONTINUE),
            )

        with a.segment(
            SEG_INTERRUPT,
            owner=CURRENT,
            kind=MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
        ) as s:
            s.on(
                "PassMovementInterrupt",
                guard=effects.is_interrupt_responder,
                effect=effects.pass_interrupt,
                goto=SEG_INTERRUPT_RESOLVE,
            )

        with a.segment(SEG_INTERRUPT_RESOLVE, owner=NO_OWNER) as s:
            s.auto_branch(
                case(guard=interrupt_queue_empty, resume=True),
                case(goto=SEG_INTERRUPT),
            )

    return a.build()


__all__ = ["build_movement_arc"]
