"""Hexdemo combat transition helpers (engine boundary phase C/D)."""

from __future__ import annotations

from dataclasses import replace

from hexengine.hooks.attack import (
    AfterAttackAppliedContext,
    AttackContext,
    AttackResolution,
    RetreatObligationClearedContext,
)
from hexengine.hexes.types import Hex
from hexengine.state import GameState
from hexengine.state.action_manager import ActionManager
from hexengine.state.actions import ClearUnitRetreatObligation, PatchTitleBucket
from hexengine.state.title_extension import title_bucket

from games.hexdemo import combat_transitions


def test_follow_up_after_attack_opens_disrupt_gate() -> None:
    st = GameState.create_empty().with_title_state(
        {combat_transitions.GATE_AWAITING_RETREAT: True},
        title_bucket_key="hexdemo",
    )
    st = st.with_title_state(
        {"combat_gate": combat_transitions.GATE_AWAITING_RETREAT},
        title_bucket_key="hexdemo",
    )
    ctx = AfterAttackAppliedContext(
        state=st,
        attack_context=AttackContext(
            state=st,
            attacker_ids=("a",),
            defender_ids=("d",),
            attacker_hexes=(Hex(0, 0, 0),),
            defender_hexes=(Hex(1, 0, -1),),
            player_faction="union",
            attack_kind="combined",
            params={},
        ),
        resolution=AttackResolution(
            outcome="defender_retreat",
            retreat_distance=2,
            effects={"retreat": {"allow_disrupt_instead": True}},
        ),
        extension_key="hexdemo",
        player_faction="union",
    )
    actions = combat_transitions.follow_up_after_attack(ctx)
    assert len(actions) == 2
    assert all(isinstance(a, PatchTitleBucket) for a in actions)
    st2 = ctx.state
    for a in actions:
        st2 = a.apply(st2)
    assert (
        title_bucket(st2, "hexdemo")["combat_gate"]
        == combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT
    )


def test_clear_unit_retreat_obligation_uses_patch_title_bucket() -> None:
    st = GameState.create_empty().with_title_state(
        {
            "combat_gate": combat_transitions.GATE_AWAITING_RETREAT,
            "retreat_obligations": {"u1": 2, "u2": 1},
        },
        title_bucket_key="hexdemo",
    )
    mgr = ActionManager(st)
    mgr.execute(ClearUnitRetreatObligation("u1", "hexdemo"))
    hx = title_bucket(mgr.current_state, "hexdemo")
    assert hx["retreat_obligations"] == {"u2": 1}
    assert hx.get("combat_gate") == combat_transitions.GATE_AWAITING_RETREAT
    mgr.execute(ClearUnitRetreatObligation("u2", "hexdemo"))
    hx2 = title_bucket(mgr.current_state, "hexdemo")
    assert hx2.get("retreat_obligations") == {}
    assert "combat_gate" not in hx2


def test_on_retreat_obligation_cleared_returns_empty_without_last_combat() -> None:
    st = GameState.create_empty().with_title_bucket_key("hexdemo")
    ctx = RetreatObligationClearedContext(state=st, extension_key="hexdemo")
    assert combat_transitions.on_retreat_obligation_cleared(ctx) == []


def test_blocks_routine_phase_advance_gate_constants() -> None:
    st = GameState.create_empty().with_title_state(
        {"combat_gate": combat_transitions.GATE_AWAITING_ADVANCE},
        title_bucket_key="hexdemo",
    )
    assert combat_transitions.blocks_routine_phase_advance(st) is True
    st2 = GameState.create_empty().with_title_bucket_key("hexdemo")
    assert combat_transitions.blocks_routine_phase_advance(st2) is False


def test_dock_arc_hint_retreat_gate() -> None:
    st = GameState.create_empty()
    arc = combat_transitions.dock_arc_hint(
        state=st,
        viewer_faction="union",
        viewer_is_turn_owner=False,
        current_phase="Combat",
        gate_actions=[{"action_type": "CombatDisruptInsteadOfRetreat"}],
    )
    assert arc == combat_transitions.DOCK_ARC_RETREAT_GATE


def test_attack_planning_blocked_on_advance_gate() -> None:
    base = GameState.create_empty()
    st = base.with_turn(
        replace(
            base.turn,
            current_faction="union",
            current_phase="Combat",
            phase_actions_remaining=1,
        )
    ).with_title_state(
        {"combat_gate": combat_transitions.GATE_AWAITING_ADVANCE},
        title_bucket_key="hexdemo",
    )
    reason = combat_transitions.attack_planning_blocked_reason(st, "union")
    assert reason is not None
    assert "advance" in reason.lower()
