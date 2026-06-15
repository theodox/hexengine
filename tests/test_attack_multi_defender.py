from __future__ import annotations

from games.hexdemo.combat.disrupt import expand_disrupt_ids
from games.hexdemo.combat.step_loss import expand_step_losses
from hexengine.hexes.types import Hex
from hexengine.state import GameState
from hexengine.state.actions import AddUnit, ApplyCombatEffects, Attack


def _apply_step_losses(st: GameState, rows: list[dict[str, object]]) -> GameState:
    extra = expand_step_losses(st, rows)
    return ApplyCombatEffects({"schema": 1, **extra}).apply(st)


def _apply_disrupt(st: GameState, anchor_ids: list[str]) -> GameState:
    extra = expand_disrupt_ids(st, anchor_ids)
    return ApplyCombatEffects({"schema": 1, **extra}).apply(st)


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
    st2 = _apply_step_losses(st, [{"unit_id": "u1", "count": 1}])
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
    st2 = _apply_step_losses(st, [{"unit_id": "u1", "count": 1}])
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
    st2 = _apply_step_losses(st, [{"unit_id": "u1", "count": 1}])
    u = st2.board.units["u1"]
    assert u.active is False


def test_step_loss_sets_graphics_from_steps_table() -> None:
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
    st2 = _apply_step_losses(st, [{"unit_id": "u1", "count": 1}])
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
    st2 = _apply_step_losses(st, [{"unit_id": "a1", "count": 1}])
    u = st2.board.units["a1"]
    assert u.attributes.get("steps_lost") == 1
    assert u.attributes.get("combat") == 3
    assert u.attributes.get("morale") == 6


def test_disrupt_anchor_marks_friendly_stack_on_hex() -> None:
    st = GameState.create_empty()
    h = Hex(0, 0, 0)
    st = AddUnit("u1", "infantry", "union", h).apply(st)
    st = AddUnit("u2", "infantry", "union", h).apply(st)
    st = st.with_session_state({}, session_state_key="hexdemo")
    st2 = _apply_disrupt(st, ["u1"])
    assert st2.board.units["u1"].attributes.get("disrupted") is True
    assert st2.board.units["u2"].attributes.get("disrupted") is True


def test_disrupt_skips_enemy_units_on_same_hex() -> None:
    st = GameState.create_empty()
    h = Hex(0, 0, 0)
    st = AddUnit("u1", "infantry", "union", h).apply(st)
    st = AddUnit("e1", "infantry", "confederate", h).apply(st)
    st = st.with_session_state({}, session_state_key="hexdemo")
    st2 = _apply_disrupt(st, ["u1"])
    assert st2.board.units["u1"].attributes.get("disrupted") is True
    assert st2.board.units["e1"].attributes.get("disrupted") is not True
