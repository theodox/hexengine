"""Map-selection kind registry and dispatch (Track C.2)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (str(REPO_ROOT / "src"), str(REPO_ROOT / "games")):
    if p not in sys.path:
        sys.path.insert(0, p)

from hexengine.gamedef.interactions import InteractionKind
from hexengine.hooks.core import ENGINE_DEFAULT
from hexengine.hooks.map_selection_registry import (
    bound_map_selection_kinds,
    map_selection_kinds_in_registry,
    resolve_map_selection_preview,
)
from hexengine.hooks.title import TitleHooks
from hexengine.server.map_selection import compute_map_selection_preview


def test_registry_lists_attack_plan() -> None:
    kinds = map_selection_kinds_in_registry()
    assert InteractionKind.ATTACK_PLAN in kinds
    assert InteractionKind.RETREAT_PATH in kinds
    assert InteractionKind.PLACE_MARKER in kinds


def test_unknown_kind_returns_empty_preview() -> None:
    from hexdemo.game_config import (
        HexdemoGameDefinition,
        default_match_config,
        game_definition_from_config,
    )
    from hexengine.scenarios import load_scenario
    from hexengine.scenarios.loader import scenario_to_initial_state
    from hexengine.server.game_server import GameServer

    scenario_path = (
        REPO_ROOT / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
    )
    scenario_data = load_scenario(scenario_path)
    gd = HexdemoGameDefinition(game_definition_from_config(default_match_config()))
    first = {"faction": "union", "phase": "Combat", "max_actions": 4}
    st = scenario_to_initial_state(
        scenario_data,
        initial_faction=first["faction"],
        initial_phase=first["phase"],
        phase_actions_remaining=int(first["max_actions"]),
        schedule_index=0,
        game_definition=gd,
    )
    server = GameServer(
        initial_state=st,
        game_definition=gd,
        pack_id="hexdemo",
        pack_root=REPO_ROOT / "games" / "hexdemo",
    )
    raw = compute_map_selection_preview(
        state=st,
        player_faction="union",
        kind="not_a_real_kind",
        draft={},
        shell_ui={},
        board_hexes=server._iter_board_hexes(st),
        hooks=server.hooks,
    )
    assert raw.get("confirm_enabled") is False
    assert raw.get("panel_actions") == []


def test_hexdemo_bound_kinds_includes_attack_plan() -> None:
    from games.hexdemo.hooks import build_hooks

    bound = bound_map_selection_kinds(build_hooks())
    assert InteractionKind.ATTACK_PLAN in bound
    assert InteractionKind.RETREAT_PATH in bound
    assert InteractionKind.PLACE_MARKER in bound


def test_unbound_hooks_yields_no_kinds() -> None:
    assert bound_map_selection_kinds(TitleHooks()) == frozenset()


def test_resolve_unknown_kind_is_engine_default() -> None:
    raw = resolve_map_selection_preview(
        state=None,
        player_faction="union",
        kind="bogus",
        draft={},
        shell_ui={},
        hooks=TitleHooks(),
    )
    assert raw is ENGINE_DEFAULT
