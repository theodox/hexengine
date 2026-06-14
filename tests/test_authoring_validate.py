"""Load-time arc contract validation (hexengine.authoring.validate)."""

from __future__ import annotations

import pytest

from hexengine.arcs import ArcSpec
from hexengine.arcs.registry import TurnArcRegistry
from hexengine.arcs.schedule import ArcSchedule, ScheduleSlot
from hexengine.authoring.validate import validate_arc_contract
from hexengine.hooks.arcs import ArcsHooks
from hexengine.hooks.interaction import InteractionHooks
from hexengine.hooks.core import HookContractError
from hexengine.hooks.internal.contracts import validate_title_contract
from hexengine.hooks.title import TitleHooks


def test_validate_arc_contract_catches_missing_routine_spec() -> None:
    slot = ScheduleSlot("union_move", "union", "Move", 4, ui_mode="move")
    reg = TurnArcRegistry(schedule=ArcSchedule((slot,)), routine_specs={})
    bundle = TitleHooks(arcs=ArcsHooks(turn_arc_registry=lambda: reg))
    errors = validate_arc_contract(bundle)
    assert any("union_move" in e for e in errors)


def test_validate_arc_contract_passes_hexdemo_registry() -> None:
    from games.hexdemo.arcs.turn_schedule import build_hexdemo_turn_arc_registry

    reg = build_hexdemo_turn_arc_registry()
    bundle = TitleHooks(arcs=ArcsHooks(turn_arc_registry=lambda: reg))
    assert validate_arc_contract(bundle) == []


def test_validate_title_contract_runs_arc_validation() -> None:
    from games.hexdemo.game_config import (
        default_match_config,
        game_definition_from_config,
    )

    gd = game_definition_from_config(default_match_config())
    validate_title_contract(gd)


def test_validate_title_contract_fails_on_broken_combat_arc() -> None:
    from hexengine.arcs import NO_OWNER, Arc, Segment
    from hexengine.arcs.spec import Event, Goto, Transition

    bad_arc = Arc(
        id="bad",
        entry="only",
        segments=(
            Segment(
                id="only",
                owner=NO_OWNER,
                transitions=(
                    Transition(
                        trigger=Event("MoveUnit"),
                        target=Goto(segment="missing_segment"),
                    ),
                ),
            ),
        ),
    )
    broken = ArcSpec(arc=bad_arc, owner_resolver=None)
    bundle = TitleHooks(
        arcs=ArcsHooks(combat_arc=lambda: broken),
        interaction=InteractionHooks(
            validate_attack=lambda _c: None,
            resolve_attack=lambda _c: None,
        ),
    )

    class _GD:
        game_data = type("GD", (), {"session_state_key": ""})()

        hooks = bundle

        def turn_order(self):
            return []

    with pytest.raises(HookContractError, match="arc contract"):
        validate_title_contract(_GD())
