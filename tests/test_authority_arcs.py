"""Smoke tests for `hexengine.server.arcs.authority_movement` and `authority_combat_cleanup` helpers."""

from __future__ import annotations

from games.hexdemo import combat_actions
from hexengine.hooks.attack import AttackHooks
from hexengine.hooks.title import TitleHooks
from hexengine.server.arcs.authority_combat_cleanup import (
    move_unit_is_combat_advance_fulfillment,
)
from hexengine.server.arcs.authority_movement import (
    dedupe_faction_ids,
    path_tuple_from_movement_arc,
    read_movement_arc,
)
from hexengine.state import GameState
from hexengine.state.game_state import BoardState, TurnState

_ADVANCE_HOOKS = TitleHooks(
    attack=AttackHooks(
        is_combat_advance_move=lambda ctx: combat_actions.is_combat_advance_move(
            ctx.state, ctx.params, ctx.player_faction, ctx.extension_key
        )
    )
)


def _minimal_state(
    *,
    title_state: dict | None = None,
    title_bucket_key: str = "title",
) -> GameState:
    return GameState(
        turn=TurnState(
            current_faction="union",
            current_phase="movement",
            phase_actions_remaining=1,
        ),
        board=BoardState(),
        title_state=dict(title_state or {}),
        title_bucket_key=title_bucket_key,
    )


def test_dedupe_faction_ids_order_and_trim() -> None:
    assert dedupe_faction_ids((" a ", "b", "a", "", "b")) == ("a", "b")


def test_read_movement_arc_missing() -> None:
    st = _minimal_state()
    assert read_movement_arc(st) is None


def test_path_tuple_from_movement_arc() -> None:
    arc = {"path": [{"i": 0, "j": 0, "k": 0}, {"i": 1, "j": -1, "k": 0}]}
    pts = path_tuple_from_movement_arc(arc)
    assert len(pts) == 2
    assert (pts[0].i, pts[0].j, pts[0].k) == (0, 0, 0)


def test_move_unit_is_combat_advance_fulfillment_false_without_extension() -> None:
    st = _minimal_state(
        title_state={
            "combat_gate": "awaiting_advance",
            "advance": {
                "faction": "union",
                "to_hex": {"i": 1, "j": 0, "k": -1},
                "unit_ids": ["u1"],
            },
        },
    )
    params = {
        "unit_id": "u1",
        "to_hex": {"i": 1, "j": 0, "k": -1},
    }
    assert not move_unit_is_combat_advance_fulfillment(
        _ADVANCE_HOOKS,
        st,
        params,
        player_faction="union",
        extension_key=None,
    )


def test_move_unit_is_combat_advance_fulfillment_true_when_matched() -> None:
    st = _minimal_state(
        title_state={
            "combat_gate": "awaiting_advance",
            "advance": {
                "faction": "union",
                "to_hex": {"i": 1, "j": 0, "k": -1},
                "unit_ids": ["u1"],
            },
        },
    )
    params = {
        "unit_id": "u1",
        "to_hex": {"i": 1, "j": 0, "k": -1},
    }
    assert move_unit_is_combat_advance_fulfillment(
        _ADVANCE_HOOKS,
        st,
        params,
        player_faction="union",
        extension_key="title",
    )
