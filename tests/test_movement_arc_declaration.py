"""Engine movement arc declaration parity with gate strings (composable arcs, Phase 3a)."""

from __future__ import annotations

from types import SimpleNamespace

from hexengine.arcs import CURRENT, NO_OWNER, ArcContext, OwnerRef
from hexengine.arcs.movement_arc_decl import (
    MOVEMENT_ARC_ID,
    OWNER_MOVING,
    SEG_CONTINUE,
    SEG_INTERRUPT,
    SEG_INTERRUPT_RESOLVE,
    SEG_STEP_RESOLVE,
    resolve_moving_faction,
)
from hexengine.authoring.patterns.movement import build_movement_arc
from hexengine.state import GameState
from hexengine.state.movement_arc import (
    HEXENGINE_MOVEMENT_ARC_KEY,
    MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
    MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
)


class _StubEffects(SimpleNamespace):
    """No-op effects binding; guards always pass/fail as configured for build()."""

    def matches_stepwise_step(self, _ctx: ArcContext) -> bool:
        return True

    def apply_step(self, _ctx: ArcContext) -> list:
        return []

    def finish_path(self, _ctx: ArcContext) -> list:
        return []

    def is_interrupt_responder(self, _ctx: ArcContext) -> bool:
        return True

    def pass_interrupt(self, _ctx: ArcContext) -> list:
        return []


def test_arc_builds_and_validates() -> None:
    build_movement_arc(_StubEffects())  # build() validates by default


def test_entry_is_continue() -> None:
    assert build_movement_arc(_StubEffects()).entry == SEG_CONTINUE


def test_arc_id() -> None:
    assert build_movement_arc(_StubEffects()).id == MOVEMENT_ARC_ID


def test_segment_owners() -> None:
    a = build_movement_arc(_StubEffects())
    assert a.get(SEG_CONTINUE).owner == OwnerRef(OWNER_MOVING)
    assert a.get(SEG_STEP_RESOLVE).owner is NO_OWNER
    assert a.get(SEG_INTERRUPT).owner is CURRENT
    assert a.get(SEG_INTERRUPT_RESOLVE).owner is NO_OWNER


def test_allowed_actions_match_gate_table() -> None:
    a = build_movement_arc(_StubEffects())
    assert a.get(SEG_CONTINUE).allowed_actions == frozenset({"MoveUnit"})
    assert a.get(SEG_STEP_RESOLVE).allowed_actions == frozenset()
    assert a.get(SEG_INTERRUPT).allowed_actions == frozenset({"PassMovementInterrupt"})
    assert a.get(SEG_INTERRUPT_RESOLVE).allowed_actions == frozenset()


def test_gate_segments_map_one_to_one_with_blocking_gates() -> None:
    a = build_movement_arc(_StubEffects())
    by_kind = {s.ui_mode: s.id for s in a.segments if s.ui_mode}
    assert set(by_kind) == {
        MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
        MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
    }
    assert by_kind[MOVEMENT_ARC_GATE_AWAITING_CONTINUE] == SEG_CONTINUE
    assert by_kind[MOVEMENT_ARC_GATE_AWAITING_INTERRUPT] == SEG_INTERRUPT


def test_owner_resolver_finds_moving_faction() -> None:
    st = GameState.create_empty()
    st = st.with_engine_state(
        {
            HEXENGINE_MOVEMENT_ARC_KEY: {
                "moving_faction": "Red",
                "gate": MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
            }
        }
    )
    assert resolve_moving_faction(OWNER_MOVING, st) == "Red"


def test_owner_resolver_none_without_payload() -> None:
    assert resolve_moving_faction(OWNER_MOVING, GameState.create_empty()) is None
