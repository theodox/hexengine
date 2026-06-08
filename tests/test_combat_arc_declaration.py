"""Hexdemo combat arc declaration parity with the gate FSM (composable arcs, Phase 2a)."""

from __future__ import annotations

from games.hexdemo import combat_arc, combat_transitions

from hexengine.arcs import CURRENT, NO_OWNER, OwnerRef
from hexengine.hexes.types import Hex
from hexengine.state import GameState
from hexengine.state.game_state import UnitState


def test_arc_builds_and_validates() -> None:
    combat_arc.build_combat_arc()  # build() validates by default


def test_entry_is_classify() -> None:
    assert combat_arc.build_combat_arc().entry == combat_arc.SEG_CLASSIFY


def test_segment_owners() -> None:
    a = combat_arc.build_combat_arc()
    assert a.get(combat_arc.SEG_CLASSIFY).owner is NO_OWNER
    assert a.get(combat_arc.SEG_RESOLVE).owner is NO_OWNER
    assert a.get(combat_arc.SEG_RETREAT_GATE).owner == OwnerRef("retreating")
    assert a.get(combat_arc.SEG_RETREAT_OR_DISRUPT_GATE).owner == OwnerRef("retreating")
    assert a.get(combat_arc.SEG_ADVANCE_GATE).owner is CURRENT


def test_attack_segment_allows_attack_rpc() -> None:
    a = combat_arc.build_combat_arc()
    assert a.get(combat_arc.SEG_ATTACK).allowed_actions == frozenset({"Attack"})


def test_allowed_actions_match_gate_table() -> None:
    a = combat_arc.build_combat_arc()
    assert a.get(combat_arc.SEG_CLASSIFY).allowed_actions == frozenset()
    assert a.get(combat_arc.SEG_RESOLVE).allowed_actions == frozenset()
    assert a.get(combat_arc.SEG_RETREAT_GATE).allowed_actions == frozenset({"MoveUnit"})
    assert a.get(combat_arc.SEG_RETREAT_OR_DISRUPT_GATE).allowed_actions == frozenset(
        {"MoveUnit", "CombatDisruptInsteadOfRetreat"}
    )
    assert a.get(combat_arc.SEG_ADVANCE_GATE).allowed_actions == frozenset(
        {"CombatAdvance", "MoveUnit", "CombatDeclineAdvance"}
    )


def test_disrupt_only_offered_in_the_disrupt_gate() -> None:
    a = combat_arc.build_combat_arc()
    assert (
        "CombatDisruptInsteadOfRetreat"
        not in a.get(combat_arc.SEG_RETREAT_GATE).allowed_actions
    )


def test_gate_segments_map_one_to_one_with_blocking_gates() -> None:
    """Each blocking gate ui_mode has exactly one segment carrying that value."""

    a = combat_arc.build_combat_arc()
    by_kind = {
        s.ui_mode: s.id
        for s in a.segments
        if s.ui_mode in combat_transitions.GATES_BLOCKING_ROUTINE
    }
    assert set(by_kind) == set(combat_transitions.GATES_BLOCKING_ROUTINE)
    assert (
        by_kind[combat_transitions.GATE_AWAITING_RETREAT] == combat_arc.SEG_RETREAT_GATE
    )
    assert (
        by_kind[combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT]
        == combat_arc.SEG_RETREAT_OR_DISRUPT_GATE
    )
    assert (
        by_kind[combat_transitions.GATE_AWAITING_ADVANCE] == combat_arc.SEG_ADVANCE_GATE
    )


def _state_with_obligation(faction: str) -> GameState:
    unit = UnitState(
        unit_id="u1", unit_type="inf", faction=faction, position=Hex(0, 0, 0)
    )
    state = GameState.create_empty()
    state = state.with_board(state.board.with_unit(unit))
    return state.with_title_state(
        {"retreat_obligations": {"u1": 1}}, title_bucket_key="hexdemo"
    )


def test_owner_resolver_finds_retreating_faction() -> None:
    state = _state_with_obligation("Blue")
    assert combat_arc.resolve_owner_ref("retreating", state) == "Blue"


def test_owner_resolver_unknown_key_is_none() -> None:
    state = _state_with_obligation("Blue")
    assert combat_arc.resolve_owner_ref("attacker", state) is None


def test_owner_resolver_none_when_no_obligation() -> None:
    state = GameState.create_empty().with_title_state({}, title_bucket_key="hexdemo")
    assert combat_arc.resolve_owner_ref("retreating", state) is None
