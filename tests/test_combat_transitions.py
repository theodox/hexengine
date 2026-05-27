"""Hexdemo combat transition helpers (engine boundary phase C)."""

from __future__ import annotations

from hexengine.hooks.attack import (
    AfterAttackAppliedContext,
    AttackContext,
    AttackResolution,
    RetreatObligationClearedContext,
)
from hexengine.state import GameState
from hexengine.state.action_manager import ActionManager
from hexengine.state.actions import ClearUnitRetreatObligation, PatchTitleBucket

from games.hexdemo import combat_transitions


def test_follow_up_after_attack_opens_disrupt_gate() -> None:
    st = GameState.create_empty().with_extension(
        {
            "hexdemo": {
                "combat_gate": combat_transitions.GATE_AWAITING_RETREAT,
            }
        }
    )
    ctx = AfterAttackAppliedContext(
        state=st,
        attack_context=AttackContext(
            state=st,
            attacker_ids=("a",),
            defender_ids=("d",),
            attacker_hexes=(),
            defender_hexes=(),
            player_faction="union",
            attack_kind="combined",
            params={},
        ),
        resolution=AttackResolution(
            outcome="defender_retreat",
            effects={"retreat": {"allow_disrupt_instead": True}},
        ),
        extension_key="hexdemo",
        player_faction="union",
    )
    actions = combat_transitions.follow_up_after_attack(ctx)
    assert len(actions) == 1
    assert isinstance(actions[0], PatchTitleBucket)
    st2 = actions[0].apply(st)
    assert (
        st2.extension["hexdemo"]["combat_gate"]
        == combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT
    )


def test_clear_unit_retreat_obligation_uses_patch_title_bucket() -> None:
    st = GameState.create_empty().with_extension(
        {
            "hexdemo": {
                "combat_gate": combat_transitions.GATE_AWAITING_RETREAT,
                "retreat_obligations": {"u1": 2, "u2": 1},
            }
        }
    )
    mgr = ActionManager(st)
    mgr.execute(ClearUnitRetreatObligation("u1", "hexdemo"))
    hx = mgr.current_state.extension["hexdemo"]
    assert hx["retreat_obligations"] == {"u2": 1}
    assert hx.get("combat_gate") == combat_transitions.GATE_AWAITING_RETREAT
    mgr.execute(ClearUnitRetreatObligation("u2", "hexdemo"))
    hx2 = mgr.current_state.extension["hexdemo"]
    assert hx2.get("retreat_obligations") == {}
    assert "combat_gate" not in hx2


def test_on_retreat_obligation_cleared_returns_none_without_last_combat() -> None:
    st = GameState.create_empty().with_extension({"hexdemo": {}})
    ctx = RetreatObligationClearedContext(state=st, extension_key="hexdemo")
    assert combat_transitions.on_retreat_obligation_cleared(ctx) is None
