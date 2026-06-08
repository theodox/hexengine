from __future__ import annotations

from hexengine.hexes.types import Hex
from hexengine.state import GameState
from hexengine.state.actions import AddUnit, ApplyCombatEffects, Attack


def test_attack_can_destroy_multiple_defenders_on_one_hex() -> None:
    st = GameState.create_empty(initial_faction="union", initial_phase="Combat")
    h_att = Hex(0, 0, 0)
    h_def = Hex(2, -1, -1)

    st = AddUnit("att", "inf", "union", h_att).apply(st)
    st = AddUnit("d1", "inf", "confederate", h_def).apply(st)
    st = AddUnit("d2", "inf", "confederate", h_def).apply(st)

    st = st.with_session_state({}, session_state_key="hexdemo")

    atk = Attack(
        "combined",
        "att",
        "d1",
        outcome="defender_destroyed",
        attacker_ids=("att",),
        defender_ids=("d1", "d2"),
        rng_entry={"op": "test"},
    )

    st2 = atk.apply(st)
    assert st2.board.units["d1"].active is False
    assert st2.board.units["d2"].active is False


def test_infantry_step_loss_reduces_combat_and_morale_once() -> None:
    st = GameState.create_empty()
    h = Hex(0, 0, 0)
    st = AddUnit(
        "u1",
        "infantry",
        "union",
        h,
        attributes={"combat": 6, "morale": 5, "movement": 6},
    ).apply(st)
    st = st.with_session_state({}, session_state_key="hexdemo")
    st2 = ApplyCombatEffects(
        {"schema": 1, "step_losses": [{"unit_id": "u1", "count": 1}]},
    ).apply(st)
    u = st2.board.units["u1"]
    assert u.attributes.get("steps_lost") == 1
    assert u.attributes.get("combat") == 5
    assert u.attributes.get("morale") == 4
    assert u.attributes.get("movement") == 6


def test_infantry_step_loss_uses_explicit_steps_table_when_present() -> None:
    st = GameState.create_empty()
    h = Hex(0, 0, 0)
    st = AddUnit(
        "u1",
        "infantry",
        "union",
        h,
        attributes={
            "combat": 6,
            "morale": 5,
            "movement": 6,
            "steps": [{"combat": 6, "morale": 5}, {"combat": 2, "morale": 1}],
        },
    ).apply(st)
    st = st.with_session_state({}, session_state_key="hexdemo")
    st2 = ApplyCombatEffects(
        {"schema": 1, "step_losses": [{"unit_id": "u1", "count": 1}]},
    ).apply(st)
    u = st2.board.units["u1"]
    assert u.attributes.get("steps_lost") == 1
    assert u.attributes.get("combat") == 2
    assert u.attributes.get("morale") == 1
    assert u.attributes.get("movement") == 6


def test_infantry_second_step_loss_removes_unit() -> None:
    st = GameState.create_empty()
    h = Hex(0, 0, 0)
    st = AddUnit(
        "u1",
        "infantry",
        "union",
        h,
        attributes={"combat": 5, "morale": 4, "steps_lost": 1},
    ).apply(st)
    st = st.with_session_state({}, session_state_key="hexdemo")
    st2 = ApplyCombatEffects(
        {"schema": 1, "step_losses": [{"unit_id": "u1", "count": 1}]},
    ).apply(st)
    u = st2.board.units["u1"]
    assert u.active is False


def test_step_loss_sets_graphics_from_steps_table() -> None:
    """First step loss switches `UnitState.graphics` to `steps[1].graphics` when set."""
    st = GameState.create_empty()
    h = Hex(0, 0, 0)
    st = AddUnit(
        "u1",
        "infantry",
        "union",
        h,
        graphics="union_infantry",
        attributes={
            "combat": 5,
            "morale": 4,
            "movement": 5,
            "steps": [
                {"combat": 5, "morale": 4, "graphics": "union_infantry"},
                {"combat": 4, "morale": 3, "graphics": "union_infantry_step"},
            ],
        },
    ).apply(st)
    st = st.with_session_state({}, session_state_key="hexdemo")
    st2 = ApplyCombatEffects(
        {"schema": 1, "step_losses": [{"unit_id": "u1", "count": 1}]},
    ).apply(st)
    assert st2.board.units["u1"].graphics == "union_infantry_step"


def test_artillery_step_loss_does_not_auto_reduce_combat() -> None:
    st = GameState.create_empty()
    h = Hex(0, 0, 0)
    st = AddUnit(
        "a1",
        "artillery",
        "union",
        h,
        attributes={"combat": 3, "morale": 6, "movement": 6},
    ).apply(st)
    st = st.with_session_state({}, session_state_key="hexdemo")
    st2 = ApplyCombatEffects(
        {"schema": 1, "step_losses": [{"unit_id": "a1", "count": 1}]},
    ).apply(st)
    u = st2.board.units["a1"]
    assert u.attributes.get("steps_lost") == 1
    assert u.attributes.get("combat") == 3
    assert u.attributes.get("morale") == 6
