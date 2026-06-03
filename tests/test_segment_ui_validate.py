"""P5: segment kind ⊆ presentation registry at load time."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
SRC = str(REPO_ROOT / "src")
for p in (GAMES, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from hexengine.authoring.segment_ui_validate import (
    collect_declared_segment_kinds,
    validate_segment_presentation,
)
from hexengine.hooks.arcs import ArcsHooks
from hexengine.hooks.core import HookContractError
from hexengine.hooks.internal.contracts import validate_title_contract
from hexengine.hooks.title import TitleHooks
from hexengine.hooks.ui import UIHooks


def test_collect_declared_kinds_includes_routine_and_combat_gates() -> None:
    from games.hexdemo.combat_transitions import (
        GATE_AWAITING_ADVANCE,
        GATE_AWAITING_RETREAT,
        GATE_AWAITING_RETREAT_OR_DISRUPT,
    )
    from games.hexdemo.hooks import build_hooks

    kinds = collect_declared_segment_kinds(build_hooks())
    assert "move" in kinds
    assert "combat" in kinds
    assert GATE_AWAITING_RETREAT in kinds
    assert GATE_AWAITING_RETREAT_OR_DISRUPT in kinds
    assert GATE_AWAITING_ADVANCE in kinds
    assert "classify" not in kinds
    assert "resolve" not in kinds


def test_validate_segment_presentation_catches_missing_kind() -> None:
    from dataclasses import replace

    from games.hexdemo.hooks import build_hooks
    from games.hexdemo.segment_ui import PRESENTATION_BY_SEGMENT_KIND

    incomplete = {
        k: v
        for k, v in PRESENTATION_BY_SEGMENT_KIND.items()
        if k != "combat"
    }
    bundle = replace(
        build_hooks(),
        ui=replace(
            build_hooks().ui,
            segment_presentation_registry=lambda: incomplete,
        ),
    )
    errors = validate_segment_presentation(bundle)
    assert any("combat" in e for e in errors)


def test_hexdemo_validate_title_contract_includes_segment_registry() -> None:
    from games.hexdemo.game_config import (
        default_match_config,
        game_definition_from_config,
    )

    validate_title_contract(game_definition_from_config(default_match_config()))


def test_validate_title_contract_requires_segment_registry_with_extension_key() -> None:
    from hexengine.gamedef.game_data import GameData
    from hexengine.hooks.ui_turn_action_dock import empty_turn_action_dock_for_viewer
    from hexengine.arcs.registry import TurnArcRegistry
    from games.hexdemo.turn_arc_schedule import build_hexdemo_turn_arc_registry

    class PackPartial:
        @property
        def game_data(self) -> GameData:
            return GameData.empty().replacing(title_state_extension_key="pack")

        hooks = TitleHooks(
            ui=UIHooks(turn_action_dock_for_viewer=empty_turn_action_dock_for_viewer),
            arcs=ArcsHooks(
                turn_arc_registry=lambda: build_hexdemo_turn_arc_registry()
            ),
        )

        def turn_order(self):
            return []

    with pytest.raises(HookContractError, match="segment_presentation_registry"):
        validate_title_contract(PackPartial())
