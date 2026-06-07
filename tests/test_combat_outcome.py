"""CombatOutcome bucket handoff parity with legacy follow-up helpers."""

from __future__ import annotations

from hexengine.hexes.types import Hex
from hexengine.hooks.attack import (
    AfterAttackAppliedContext,
    AttackContext,
    AttackResolution,
)
from hexengine.state import BoardState, GameState, TurnState, UnitState
from hexengine.state.actions import PatchTitleBucket

from games.hexdemo import combat_outcome, combat_transitions


def _follow_ctx(
    *,
    outcome: str = "defender_retreat",
    retreat_distance: int = 2,
    retreat_unit_id: str | None = None,
    effects: dict | None = None,
) -> AfterAttackAppliedContext:
    board = BoardState(
        units={
            "u_att": UnitState(
                unit_id="u_att",
                unit_type="inf",
                faction="union",
                position=Hex(0, 0, 0),
                active=True,
            ),
            "u_def": UnitState(
                unit_id="u_def",
                unit_type="inf",
                faction="confederate",
                position=Hex(1, 0, -1),
                active=True,
            ),
        }
    )
    turn = TurnState(
        current_faction="union",
        current_phase="Combat",
        turn_number=1,
        phase_actions_remaining=1,
    )
    st = GameState(board=board, turn=turn, title_state={}, title_bucket_key="hexdemo")
    att_h = st.board.units["u_att"].position
    def_h = st.board.units["u_def"].position
    attack_context = AttackContext(
        state=st,
        attacker_ids=("u_att",),
        defender_ids=("u_def",),
        attacker_hexes=(att_h,),
        defender_hexes=(def_h,),
        player_faction="union",
        attack_kind="combined",
        params={
            "attacker_id": "u_att",
            "defender_id": "u_def",
            "attack_kind": "combined",
        },
    )
    return AfterAttackAppliedContext(
        state=st,
        attack_context=attack_context,
        resolution=AttackResolution(
            outcome=outcome,
            retreat_distance=retreat_distance,
            retreat_unit_id=retreat_unit_id,
            effects=effects,
        ),
        extension_key="hexdemo",
        player_faction="union",
    )


def _patch_from_outcome(ctx: AfterAttackAppliedContext):
    built = combat_outcome.build_combat_outcome_after_applied(ctx)
    actions = built.follow_up_state_actions(ctx.extension_key)
    assert len(actions) == 1
    return actions[0]


def _patch_from_legacy(ctx: AfterAttackAppliedContext):
    actions = combat_transitions.follow_up_after_attack(ctx)
    assert len(actions) == 1
    return actions[0]


def test_combat_outcome_matches_legacy_retreat_follow_up() -> None:
    ctx = _follow_ctx()
    legacy = _patch_from_legacy(ctx)
    outcome = _patch_from_outcome(ctx)
    assert isinstance(legacy, PatchTitleBucket)
    assert isinstance(outcome, PatchTitleBucket)
    assert outcome.extension_key == legacy.extension_key
    assert outcome.patch == legacy.patch
    assert outcome.remove_keys == legacy.remove_keys


def test_combat_outcome_disrupt_instead_flag_parity() -> None:
    ctx = _follow_ctx(
        effects={
            "retreat": {"allow_disrupt_instead": True},
        }
    )
    legacy = _patch_from_legacy(ctx)
    outcome = _patch_from_outcome(ctx)
    assert outcome.patch.get("disrupt_instead_offered") is True
    assert legacy.patch.get("disrupt_instead_offered") is True
    assert outcome.remove_keys == ()
    assert legacy.remove_keys == ()
