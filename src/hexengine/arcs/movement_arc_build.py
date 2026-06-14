"""
Engine stepwise movement arc graph (host-bound effects injected at assembly time).

Title packs opt in via ``ArcHook.MOVEMENT_ARC`` returning ``ENGINE_MOVEMENT_ARC_PRESET``
or assemble their own ``ArcSpec`` with ``MovementArcEffectsBinding`` implementations.
"""

from __future__ import annotations

from .movement_arc_decl import (
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
from .spec import (
    AUTO,
    CURRENT,
    Event,
    FlowEnd,
    Goto,
    Interrupt,
    NO_OWNER,
    Arc,
    OwnerRef,
    Segment,
    Transition,
)


def build_movement_arc(effects: MovementArcEffectsBinding) -> Arc:
    """Build the engine stepwise movement arc (interrupt sub-arc, depth-1 suspend)."""

    return Arc(
        id=MOVEMENT_ARC_ID,
        entry=SEG_CONTINUE,
        segments=(
            Segment(
                id=SEG_CONTINUE,
                owner=OwnerRef(OWNER_MOVING),
                ui_mode=MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
                transitions=(
                    Transition(
                        trigger=Event("MoveUnit"),
                        guard=effects.matches_stepwise_step,
                        effect=effects.apply_step,
                        target=Goto(segment=SEG_STEP_RESOLVE),
                    ),
                ),
            ),
            Segment(
                id=SEG_STEP_RESOLVE,
                owner=NO_OWNER,
                transitions=(
                    Transition(
                        trigger=AUTO,
                        guard=path_complete,
                        effect=effects.finish_path,
                        target=FlowEnd.DONE,
                    ),
                    Transition(
                        trigger=AUTO,
                        guard=step_opened_interrupts,
                        target=Interrupt(segment=SEG_INTERRUPT, resume=SEG_CONTINUE),
                    ),
                    Transition(
                        trigger=AUTO,
                        target=Goto(segment=SEG_CONTINUE),
                    ),
                ),
            ),
            Segment(
                id=SEG_INTERRUPT,
                owner=CURRENT,
                ui_mode=MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
                transitions=(
                    Transition(
                        trigger=Event("PassMovementInterrupt"),
                        guard=effects.is_interrupt_responder,
                        effect=effects.pass_interrupt,
                        target=Goto(segment=SEG_INTERRUPT_RESOLVE),
                    ),
                ),
            ),
            Segment(
                id=SEG_INTERRUPT_RESOLVE,
                owner=NO_OWNER,
                transitions=(
                    Transition(
                        trigger=AUTO,
                        guard=interrupt_queue_empty,
                        target=FlowEnd.RESUME,
                    ),
                    Transition(
                        trigger=AUTO,
                        target=Goto(segment=SEG_INTERRUPT),
                    ),
                ),
            ),
        ),
    )


__all__ = ["build_movement_arc"]
